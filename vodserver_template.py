import socket, sys
import datetime
import os

BUFSIZE = 1024
LARGEST_CONTENT_SIZE = 5242880

class Vod_Server():
    def __init__(self, port_id):
        # create an HTTP port to listen to
        self.http_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.http_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.http_socket.bind(("", port_id))
        self.http_socket.listen(10000)
        self.remain_threads = True

        # load all contents in the buffer
        self.load_contents("content")
        # listen to the http socket
        self.listen()
        pass

    def load_contents(self, dir):
        #Create a list of files and stuff that you have
        self.contentlist = {}
        for root, dirs, files in os.walk(dir):
            for filename in files:
                filepath = os.path.join(root,filename)
                if os.path.isfile(filepath):
                    relpath = os.path.relpath(filepath, dir)
                    self.contentlist[relpath] = filepath
                #more to do?
        return

    def listen(self):
        while self.remain_threads:
            connection_socket, client_address = self.http_socket.accept()
            try:
                msg_string = connection_socket.recv(BUFSIZE).decode()
                #Do stuff here.
                #NOTE: if we want concurrent stuff i think we have to add more threading here but its not required idgaf
                self.response(msg_string, connection_socket)
            finally:
                connection_socket.close() #unsure about this?
            
        return
    
    def response(self, msg_string, connection_socket):
        #Do based on the situation if the files exist, do not exist or are unable to respond due to confidentiality
        lines = msg_string.split('\r\n')
        if len(lines[0].split()) <3:
            return #return error for malformed? close?

        method, url, http_ver = lines[0].split()
        header = self.eval_commands(lines[1:])

        if method != "GET":
            return

        #do reponse logic now:

        #psuedocode:
        # relpath = url.lstrip('/')
        # 403 forbidden error:
        # if "/confidential/" in url: # or relpath.startswith
        #     self.generate_response_403(http_ver, connection_socket)
        #     return

        # 404 not found error:
        # if relpath not in self.contentlist:
        #    self.generate_response_404(http_ver, connection_socket)
        #    return

        #206 partial error, 200 OK
        # need to extract file type too like: filetype = relpath,split('.')[-1]
        # if "Range" in header:
        #     self.generate_response_206()
        # else:
        #     self.generate_response_200()

        return
    
    def generate_response_404(self, http_version, connection_socket):
        #Generate Response and Send
        
        return response

    def generate_response_403(self, http_version, connection_socket):
        #Generate Response and Send
        
        return response
    
    def generate_response_200(self, http_version, file_idx, file_type, connection_socket):
        #Generate Response and Send
        #this will call generate content type
        return response

    def generate_response_206(self, http_version, file_idx, file_type, command_parameters, connection_socket):
        #Generate Response and Send
        #this will call generate content type
        return response

    def generate_content_type(self, file_type):
        #Generate Headers
        
        return ""

    def eval_commands(self, commands):
        command_dict = {}
        for item in commands[1:]:
            item = item.rstrip()
            splitted_item = item.split(":")
            command_dict[splitted_item[0]] = splitted_item[1].strip()
        return command_dict

if __name__ == "__main__":
    Vod_Server(int(sys.argv[1]))