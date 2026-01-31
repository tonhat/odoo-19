import erppeek
client = erppeek.Client('http://localhost:8077', 'odoo-19', 'admin', '1')
connect_obj = erppeek.Model(client, 'init_connect_gpt.service')
result = connect_obj.prompt("Write a short reply.", system="You are a helpful assistant.")
print(result["content"])

result = connect_obj.prompt("you known config LLM into Odoo-18", system="You are a helpful assistant.")