import socket

HOST = "localhost"
PORT = 1234
MAX_CONN = 5
PREFIX = "/proxy/"


class Proxy:
    def __init__(self, host, port, max_connections=5, request_size_limit=4096,
                 reuseaddr=True, debug_level=0):
        self.host = host
        self.port = port
        self.max_connections = max_connections
        self.request_size_limit = request_size_limit
        self.reuseaddr = reuseaddr
        self.debug_level = debug_level
        self.server_socket = None

    def run(self):
        self._bind()
        self._listen()
        self._accept()

    def _bind(self):
        try:
            print("Binding to {}:{}".format(self.host, self.port))
            self.server_socket = \
                socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Set option to reuse address on bind
            if self.reuseaddr:
                self.server_socket.setsockopt(
                    socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
        except socket.error:
            print("Unable to bind to {}:{}, exiting.".format(self.host,
                                                             self.port))
            exit(1)

    # Listen step
    def _listen(self):
        try:
            self.server_socket.listen(self.max_connections)
        except socket.error:
            print("Unable to listen, exiting.")
            exit(2)

    # Accept step
    def _accept(self):
        while True:
            try:
                client_socket, client_address = self.server_socket.accept()
                if self.debug_level >= 1:
                    print("New client from: {}".format(client_address))
                self.client_request(client_socket, client_address)
                client_socket.close()
            except KeyboardInterrupt:
                if self.debug_level >= 1:
                    print("Keyboard interruption reached. Closing server.")
                self.server_socket.close()
                exit(0)
            except socket.error:
                print("Unable to get client connection.")

    def client_request(self, client_socket, client_address):
        request = client_socket.recv(self.request_size_limit)
        # Handle prefix heere
        url, request = self.prepare_request(request)
        self.proxy_request(url, 80, request, client_socket)

    def get_url(self, first_line):
        url = first_line.split(' ')[1]
        # If url starts with '/'
        if url.startswith('/'):
            url = url[1:]
        if url.startswith("http://"):
            url = url[7:]
        after_slash = url.find('/')
        # Slash is found
        if after_slash != -1:
            return url[:after_slash], url[after_slash:]
        else:
            return url, '/'

    def prepare_request(self, request):
        rewritten_url = False
        rewritten_host = False
        decoded_request = request.decode("utf-8")
        base_url = ""
        new_request = ""
        for line in decoded_request.split("\r\n"):
            if not rewritten_url:
                base_url, end_url = self.get_url(line)
                a = line.split(' ')
                new_request = "{} {} {}".format(a[0], end_url, a[2])
                rewritten_url = True
            elif not rewritten_host and line.startswith("Host:"):
                new_request += "\r\nHost: {}".format(base_url)
                rewritten_host = True
            else:
                new_request += "\r\n{}".format(line)
        return base_url, str.encode(new_request)

    def proxy_request(self, url, port, request, client_socket):
        remote_connect_socket = \
            socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_connect_socket.settimeout(5)
        remote_connect_socket.connect((url, port))
        remote_connect_socket.sendall(request)
        try:
            while True:
                partial_read = \
                    remote_connect_socket.recv(self.request_size_limit)
                if len(partial_read) > 0:
                    client_socket.send(partial_read)
                else:
                    break
            remote_connect_socket.close()
        except Exception as e:
            print(e)
            remote_connect_socket.close()


if __name__ == "__main__":
    p = Proxy(HOST, PORT, debug_level=2, request_size_limit=4096)
    p.run()
