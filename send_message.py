# Download the helper library from https://www.twilio.com/docs/python/install
import os
from twilio.rest import Client

account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
client = Client(account_sid, auth_token)

message = client.messages.create( 
                              from_='+12313665808', 
                              body ='''

                              Hey Yash, Sudhir just added a new expense to the group:

Item/Description: Trial
Amount: 0
Paid by: Sudhir

Your share: 0

Feel free to check it out on https://splitease.in''', 
                              to ='+918295939353'
                          ) 
  
print(message) 
