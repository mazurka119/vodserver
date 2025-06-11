import socket, sys
import datetime
import os
import mimetypes

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
                    relpath = os.path.relpath(filepath, dir).replace("\\","/") #to make sure that all the paths are normalized
                    self.contentlist["/"+relpath] = filepath
        return

    def listen(self):
        while self.remain_threads:
            connection_socket, client_address = self.http_socket.accept()
            try:
                msg_string = connection_socket.recv(BUFSIZE).decode()
                self.response(msg_string, connection_socket)
            finally:
                connection_socket.close() #unsure about this?
            
        return
    
    def response(self, msg_string, connection_socket):
        #Do based on the situation if the files exist, do not exist or are unable to respond due to confidentiality
        lines = msg_string.split('\r\n')
        if len(lines[0].split()) <3:
            return #return if its malformed
        
        method, url, http_ver = lines[0].split()
        header = self.eval_commands(lines[1:])

        if method != "GET":
            return
        
        relpath = url if url.startswith("/") else "/" + url
        if relpath in self.contentlist:
            path = self.contentlist[relpath]
        else:
            self.generate_response_404(http_ver, connection_socket)
            return
        if "confidential" in relpath or "confidential" in path:
            self.generate_response_403(http_ver, connection_socket)
            return

        size = os.path.getsize(path)
        #check for 206 range header / ignoring case
        has_range = any(key.lower() == 'range' for key in header.keys())
        
        if has_range:
            self.generate_response_206(http_ver, connection_socket, path, url, header)
        elif size > LARGEST_CONTENT_SIZE:
            self.generate_response_206_full(http_ver, connection_socket, path, url)
        else:
            self.generate_response_200(http_ver, connection_socket, path, url)

    
    def generate_response_404(self, http_version, connection_socket):
        #Generate Response and Send
        response_line = f"{http_version} 404 Not Found\r\n"
        headers = "Content-Type: text/html\r\n"
        headers += f"Date: {datetime.datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')}\r\n"
        headers += f"Content-Length: 85\r\n"
        headers += "Connection: close\r\n"
        headers += "\r\n"
        
        body = "<html><body><h1>404 Not Found</h1><p>The requested file was not found on this server.</p></body></html>"
        
        response = response_line + headers + body

        connection_socket.send(response.encode())
        return response

    def generate_response_403(self, http_version, connection_socket):
        #Generate Response and Send
        response_line = f"{http_version} 403 Forbidden\r\n"
        headers = "Content-Type: text/html\r\n"
        headers += f"Date: {datetime.datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')}\r\n"
        headers += f"Content-Length: 78\r\n"
        headers += "Connection: close\r\n"
        headers += "\r\n"
        
        body = "<html><body><h1>403 Forbidden</h1><p>Access to this resource is forbidden.</p></body></html>"
        
        response = response_line + headers + body
        connection_socket.send(response.encode())
        return response
    
    def generate_response_200(self, http_version, connection_socket, file_path, relpath):
        try:
            file_size = os.path.getsize(file_path)
            
            # For large files, we should always support range requests
            response_line = f"{http_version} 200 OK\r\n"
            headers = f"Content-Type: {self.generate_content_type(relpath)}\r\n"
            headers += f"Content-Length: {file_size}\r\n"
            headers += f"Date: {datetime.datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')}\r\n"
            headers += "Accept-Ranges: bytes\r\n"
            headers += "Connection: close\r\n"
            headers += "\r\n"
        
            connection_socket.send((response_line + headers).encode())
            
            #chunking large files
            with open(file_path, 'rb') as file:
                while True:
                    chunk = file.read(8192)  # 8KB chunks
                    if not chunk:
                        break
                    connection_socket.send(chunk)
            
            response = response_line + headers
            return response
            
        except Exception as e:
            self.generate_response_404(http_version, connection_socket)
            return None

    #large files that dont have a range header
    def generate_response_206_full(self, http_version, connection_socket, file_path, relpath):
        try:
            file_size = os.path.getsize(file_path)
            
            #send just the first chunk for large files
            begin = 0
            end = min(LARGEST_CONTENT_SIZE - 1, file_size - 1)
            content_length = end - begin + 1
            
            # Read the specified range
            with open(file_path, 'rb') as file:
                file.seek(begin)
                file_content = file.read(content_length)
            
            response_line = f"{http_version} 206 Partial Content\r\n"
            headers = f"Content-Type: {self.generate_content_type(relpath)}\r\n"
            headers += f"Content-Length: {content_length}\r\n"
            headers += f"Content-Range: bytes {begin}-{end}/{file_size}\r\n"

            headers += f"Date: {datetime.datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')}\r\n"
            headers += "Accept-Ranges: bytes\r\n"
            headers += "Connection: close\r\n"
            headers += "\r\n"
            
            connection_socket.send((response_line + headers).encode())
            connection_socket.send(file_content)
            
            response = response_line + headers
            return response
            
        except Exception as e:
            self.generate_response_404(http_version, connection_socket)
            return None

    def generate_response_206(self, http_version, connection_socket, file_path, relpath, command_parameters):
        #generate Response and Send for large files with range headers
        try:
            file_size = os.path.getsize(file_path)
            
            # Parse Range header (case-insensitive)
            range_header = None
            for key, value in command_parameters.items():
                if key.lower() == 'range':
                    range_header = value
                    break
            
            start = 0
            end = file_size - 1
            
            if range_header and range_header.startswith('bytes='):
                range_spec = range_header[6:]
                if '-' in range_spec:
                    range_start, range_end = range_spec.split('-', 1)
                    if range_start:
                        start = int(range_start)
                    if range_end:
                        end = min(int(range_end), file_size - 1)
                    else:
                        # If no end specified, limit to LARGEST_CONTENT_SIZE
                        end = min(start + LARGEST_CONTENT_SIZE - 1, file_size - 1)
            
            # Ensure we don't exceed the maximum content size
            if end - start + 1 > LARGEST_CONTENT_SIZE:
                end = start + LARGEST_CONTENT_SIZE - 1
            
            # Read the specified range
            with open(file_path, 'rb') as file:
                file.seek(start)
                content_length = end - start + 1
                file_content = file.read(content_length)
            
            response_line = f"{http_version} 206 Partial Content\r\n"
            headers = f"Content-Type: {self.generate_content_type(relpath)}\r\n"
            headers += f"Content-Length: {content_length}\r\n"
            headers += f"Content-Range: bytes {start}-{end}/{file_size}\r\n"
            headers += f"Date: {datetime.datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')}\r\n"
            headers += "Accept-Ranges: bytes\r\n"
            headers += "Connection: close\r\n"
            headers += "\r\n"
            
            
            connection_socket.send((response_line + headers).encode())
            connection_socket.send(file_content)
            
            response = response_line + headers
            return response
            
        except Exception as e:
            self.generate_response_404(http_version, connection_socket)
            return None

    def generate_content_type(self, file_path):
        #mimetypes 
        mime_type, _ = mimetypes.guess_type(file_path)
        
        if mime_type:
            return mime_type
        
        #fallback for common video/media file types
        extension = os.path.splitext(file_path)[1].lower()
        content_types = {
            '.mp4': 'video/mp4',
            '.avi': 'video/x-msvideo',
            '.mov': 'video/quicktime',
            '.wmv': 'video/x-ms-wmv',
            '.flv': 'video/x-flv',
            '.webm': 'video/webm',
            '.mkv': 'video/x-matroska',
            '.mp3': 'audio/mpeg',
            '.ogg': 'audio/ogg',
            '.wav': 'audio/wav',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.css': 'text/css',
            '.html': 'text/html',
            '.js': 'application/javascript',
            '.json': 'application/json',
            '.txt': 'text/plain'
        }
        
        return content_types.get(extension, 'application/octet-stream')

    def eval_commands(self, commands):
        command_dict = {}
        for item in commands:
            item = item.rstrip()
            if ':' in item:
                splitted_item = item.split(":", 1)
                command_dict[splitted_item[0]] = splitted_item[1].strip()
        return command_dict

if __name__ == "__main__":
    Vod_Server(int(sys.argv[1]))