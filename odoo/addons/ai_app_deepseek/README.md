# Odoo AI Ask DeepSeek Module

[简体中文](README_zh_CN.md)

## Overview

This module extends the AI App (`ai_app`) in Odoo 19 Enterprise Edition to add support for the DeepSeek AI model. With this module, users can use their own DeepSeek account for the "Ask AI" feature in Odoo.

## Features

- **DeepSeek Model Integration**: Adds the `deepseek-chat` model as a new language model option in Odoo's AI agent.
- **Custom API Key**: Allows users to configure their own DeepSeek API key in the Odoo settings for a secure connection to the DeepSeek service.
- **Seamless Experience**: Once installed, the "Ask AI" feature will automatically gain the ability to use DeepSeek without complex additional setup.

## Installation

1.  Copy the `ai_app_deepseek` folder to your Odoo `addons` directory.
2.  Log in to Odoo with developer mode enabled.
3.  Navigate to the **Apps** menu.
4.  Click **Update Apps List**.
5.  Search for the `AI Ask DeepSeek` module and click **Install**.

## Configuration

After installation, you need to configure your DeepSeek API key to use the feature.

1.  Navigate to **Settings -> General Settings**.
2.  In the **AI** section, find the **Use your own DeepSeek account** option.
3.  Check the box to enable the custom key.
4.  Enter your DeepSeek API key (usually starting with `sk-...`) in the text box below.
5.  Click **Save**.

  <!-- It is recommended to replace this with a screenshot of the configuration page -->

## Usage

Once configured, you can use the DeepSeek model anywhere the "Ask AI" feature is integrated in Odoo.

For example, click the "Ask AI" icon in the upper right corner of the Odoo main interface, enter your question, and the system will use the configured DeepSeek model to generate a response.

## Author & Support

- **GitHub**: [https://github.com/cd-feng](https://github.com/cd-feng)

## License

This module is released under the [AGPL-3](https://www.gnu.org/licenses/agpl-3.0.html) license.
