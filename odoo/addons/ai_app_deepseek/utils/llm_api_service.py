# -*- coding: utf-8 -*-
import logging
import json
import os
from odoo import api, fields, models, exceptions
from odoo.api import Environment
from odoo.exceptions import UserError
from odoo.addons.ai.utils.ai_logging import api_call_logging
from odoo.addons.ai.utils.llm_api_service import LLMApiService
_logger = logging.getLogger(__name__)

# LLMApiService Origin
_original_init = LLMApiService.__init__
_original_get_api_token = LLMApiService._get_api_token
_original_request_llm = LLMApiService._request_llm
_original_build_tool_call_response = LLMApiService._build_tool_call_response


def new_init(self, env: Environment, provider: str = 'openai') -> None:
    if provider == 'deepseek':
        _original_init(self, env, provider='openai')
        self.provider = 'deepseek'
        self.base_url = "https://api.deepseek.com"
    else:
        _original_init(self, env, provider)


def new_get_api_token(self):
    if self.provider == 'deepseek':
        config_key = "ai.deepseek_key"
        env_var = "ODOO_AI_DEEPSEEK_TOKEN"
        api_key = self.env["ir.config_parameter"].sudo().get_param(config_key) or os.getenv(env_var)
        if api_key:
            return api_key
        raise UserError(f"No API key set for provider '{self.provider}'")
    return _original_get_api_token(self)


def new_request_llm(self, *args, **kwargs):
    if self.provider == 'deepseek':
        return self._request_llm_deepseek(*args, **kwargs)
    return _original_request_llm(self, *args, **kwargs)


def _request_llm_deepseek(self, llm_model, system_prompts, user_prompts, tools=None, files=None, schema=None, temperature=1.0, inputs=(), web_grounding=False):
    messages = []
    if system_prompts:
        messages.append({"role": "system", "content": "\n".join(system_prompts)})
    for inp in inputs:
        role = inp.get('role')
        if role == 'tool':
            messages.append({
                "role": "tool",
                "tool_call_id": inp.get("tool_call_id") or inp.get("call_id"),  # 兼容不同字段名
                "content": inp.get("content") or ""
            })
        elif role == 'assistant':
            msg = {"role": "assistant"}
            if inp.get("content"):
                msg["content"] = inp["content"]
            if inp.get("tool_calls"):
                msg["tool_calls"] = inp["tool_calls"]
            messages.append(msg)
        else:
            content_obj = inp.get('content', "")
            text_content = ""
            if isinstance(content_obj, list):
                for item in content_obj:
                    if isinstance(item, dict) and item.get('text'):
                        text_content += item['text']
            elif isinstance(content_obj, str):
                text_content = content_obj
            if text_content:
                messages.append({"role": role or "user", "content": text_content})

    current_user_text = "\n".join(user_prompts)
    if files:
        for f in files:
            if f['mimetype'] == 'text/plain':
                current_user_text += f"\n\n[File Content]:\n{f['value']}"
    messages.append({"role": "user", "content": current_user_text})
    # Create Body
    body = {
        "model": llm_model,
        "messages": messages,
        "temperature": temperature,
        "stream": False
    }
    # Processing Tools format (standard OpenAI format)
    formatted_tools = []
    if tools:
        for name, (desc, __, __, params) in tools.items():
            formatted_tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": desc,
                    "parameters": params,
                }
            })
        body["tools"] = formatted_tools
        body["tool_choice"] = "auto"

    with api_call_logging(messages, tools) as record_response:
        response, to_call, next_inputs = self._request_llm_deepseek_helper(body, tools, inputs)
        if record_response:
            record_response(to_call, response)
        return response, to_call, next_inputs


def _request_llm_deepseek_helper(self, body, tools=None, inputs=()):
    response_json = self._request("post", "/chat/completions", self._get_base_headers(), body)

    to_call = []
    response_texts = []
    next_inputs = list(inputs or ())

    choices = response_json.get("choices", [])
    if not choices:
        return [], [], next_inputs
    message = choices[0].get("message", {})
    has_tool_calls = message.get("tool_calls")  # 检查是否有工具调用
    if has_tool_calls:
        for tool_call in has_tool_calls:
            function_call = tool_call.get("function", {})
            name = function_call.get("name")
            arguments = function_call.get("arguments")
            call_id = tool_call.get("id")
            if name and tools and name in tools:
                try:
                    args_json = json.loads(arguments)
                    to_call.append((name, call_id, args_json))
                except json.JSONDecodeError:
                    _logger.error("DeepSeek: Malformed tool arguments: %s", arguments)
    content = message.get("content")
    if content:
        if not has_tool_calls:
            response_texts.append(content)
    assistant_msg = {"role": "assistant"}
    if content:
        assistant_msg["content"] = content
    if has_tool_calls:
        assistant_msg["tool_calls"] = has_tool_calls
    if content or has_tool_calls:
        next_inputs.append(assistant_msg)
    return response_texts, to_call, next_inputs


def new_build_tool_call_response(self, tool_call_id, return_value):
    if self.provider == 'deepseek':
        # DeepSeek/OpenAI Standard format
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": str(return_value),
        }
    return _original_build_tool_call_response(self, tool_call_id, return_value)


# Override original class
LLMApiService.__init__ = new_init
LLMApiService._get_api_token = new_get_api_token
LLMApiService._request_llm = new_request_llm
LLMApiService._request_llm_deepseek = _request_llm_deepseek
LLMApiService._build_tool_call_response = new_build_tool_call_response
LLMApiService._request_llm_deepseek_helper = _request_llm_deepseek_helper
