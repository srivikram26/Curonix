import requests
from requests import Session
session = Session()
response = session.post('http://127.0.0.1:5000/auth/api/register', json={
    'first_name': 'Auto',
    'last_name': 'Tester',
    'email': 'autotest123@example.com',
    'password': 'Aa12345!'
})
print('status', response.status_code)
print(response.text)
