'''
---------------------------------
Client For Socket Programming
---------------------------------
__updated__ = '2025-10-20'
Author: Luke Vrbanac, 
Email: lwvrbanac@gmail.com
---------------------------------
'''
import socket

HOST = '127.0.0.1'
HOST_SOCKET = 37200
BUFFER = 4096
TIMEOUT = 0.5

def client_main():
  #AF_INET is for 32-bit addresses like 0.0.0.0 and SOCK_STREAM is for setting up the tcp protocol
  client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

  #connect to server and let user know of success
  client.connect((HOST, HOST_SOCKET))
  print("Initial Connection successful:\n")

  #recieve initial data and relay to CLI upon success
  client_data = client.recv(BUFFER)
  client_number = client_data.decode("utf-8", errors="replace")
  print(f"{client_number}\n")

  if client_number.startswith("BUSY"):
     return

  #echo to server to acknowledge opening of connection
  client.send(client_data)

  #basic instructions for client side and initialization for input loop
  print("send a string to the server\nType 'exit' to close the client or 'status' for cache data\nType 'list' to get the repo of all files\nType the name of the file to be streamed to the client to access it")
  input_string = "temp"
  
  #input loop
  while input_string:
    input_string  = input("Enter message here: ")
    #necessary for the server to tell the message has ended, not handled automatically by CLI
    input_string += "\n"

    #send CLI command or message to server
    client.send(input_string.encode("utf-8", errors="replace"))

    #recieve and print message
    data_string = recieve_data(client)
    print(f"data recieved from server: {data_string}\n")

    #if the 'exit' command is issued break the loop and close the client
    if input_string == "exit\n" or input_string == "Exit\n":
      break
  
  client.close()

#modified copy of reception method from server
def recieve_data(client):
   #sets timeout for incoming data and reads byte by byte into bytearray
   client.settimeout(TIMEOUT)
   incoming = bytearray()

   #loops while data incoming
   while True:
      try:
         
         #recieves byte of data
         data = client.recv(1)

         #checks if connection closed, useful if sent data is "exit" otherwise timeout does not occur
         if data == b"":
            return incoming.decode()
         
         #puts read byte of data into bytearray
         incoming.extend(data)

      #breaks loop when no more data incoming
      except socket.timeout:
         break
    #returns data in human legible form
   return incoming.decode()

#runs the program  
if __name__ == "__main__":
    client_main()