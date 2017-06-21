import socket
import errno

HOST = "localhost"
PORT = 1234
MAX_CONN = 5
PREFIX = "/proxy/"


class Proxy:
    def __init__(self, host, port, prefix="", max_connections=5,
                 request_size_limit=4096, reuseaddr=True, debug_level=0):
        """
        Initialize a new Proxy class.

        :param host: address to bind the proxy server to
        :param port: port to bind the proxy server to
        :param prefix: only accept proxy requests containing this prefix
        :param max_connections: max connections the proxy can have at a time
        :param request_size_limit: how much to read from a socket
        :param reuseaddr: whether to reuse and address if it is occupied
        :param debug_level: -1 no messages, 0 regular messages,
        1 connection messages, 2 socket messages
        :type host: str
        :type port: int
        :type prefix: str
        :type max_connections: int
        :type request_size_limit: int
        :type reuseaddr: bool
        :type debug_level: int
        """
        self.host = host
        self.port = port
        self.prefix = prefix
        self.max_connections = max_connections
        self.request_size_limit = request_size_limit
        self.reuseaddr = reuseaddr
        self.debug_level = debug_level
        self.server_socket = None

    def run(self):
        """
        Run the proxy server.
        """
        self._bind()
        self._listen()
        self._accept()

    def _bind(self):
        """
        Run the bind step for setting up a server. Bind at the host and port
        that was instantiated with the class.
        """
        try:
            if self.debug_level >= 0:
                print("Binding to {}:{}".format(self.host, self.port))
            self.server_socket = \
                socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Set option to reuse address on bind
            if self.reuseaddr:
                self.server_socket.setsockopt(
                    socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
        except socket.error:
            if self.debug_level >= 0:
                print(
                    "Unable to bind to {}:{}, exiting.".format(self.host,
                                                               self.port))
            exit(1)

    def _listen(self):
        """
        Setup up server socket to listen for incoming connections.
        """
        try:
            self.server_socket.listen(self.max_connections)
        except socket.error:
            if self.debug_level >= 0:
                print("Unable to listen, exiting.")
            exit(2)

    def _accept(self):
        """
        Block until a new client connection has been made.
        """
        while True:
            try:
                # Blocking occurs here until a new client connection.
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
        """
        Handle a client's request. Check if the url contains prefix. If it
        does, proxy the client's request.

        :param client_socket: socket of the client
        :param client_address: address (host, port) of the client
        :type client_socket: socket.socket
        :type client_address: tuple
        """
        request = client_socket.recv(self.request_size_limit)
        url = Proxy.get_url(request)
        # Ignore requests without the proper prefix (self.prefix)
        if url.startswith(self.prefix):
            address, path = Proxy.separate_url_and_prefix(url, self.prefix)
            request = Proxy.prepare_request(request, address, path)
            self.proxy_request(address, 80, request,
                               client_socket, client_address)

    def proxy_request(self, remote_address, remote_port,
                      request, client_socket, client_address):
        """
        Connect to remote_address:remote_port and send the request. Retrieve
        reply and send directly to the client.

        :param remote_address: address to connect to
        :param remote_port: port of the remote address to connect to
        :param request: request of the client
        :param client_socket: socket of the client
        :param client_address: address (host, port) of the client
        :type remote_address: str
        :type remote_port: int
        :type request: bytes
        :type client_socket: socket.socket
        :type client_address: tuple
        """
        remote_connect_socket = \
            socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_connect_socket.connect((remote_address, remote_port))
        remote_connect_socket.sendall(request)
        try:
            while True:
                partial_read = \
                    remote_connect_socket.recv(self.request_size_limit)
                # Set non-blocking after first read. Catch when read is
                # empty and declare connection to be closed
                remote_connect_socket.setblocking(0)
                if len(partial_read) == 0:
                    break
                if self.debug_level >= 2:
                    print(
                        "Received data from ('{}' , {})".format(
                            remote_address, remote_port))
                    print("Sending data to {}".format(client_address))
                client_socket.send(partial_read)
            remote_connect_socket.close()
        except socket.error as e:
            err = e.args[0]
            # Connection has read all the data
            if err == errno.EAGAIN or err == errno.EWOULDBLOCK:
                remote_connect_socket.close()
            else:
                print(e)
                exit(3)

    @staticmethod
    def get_url(request):
        """
        Decode a request and extract the url.

        :param request: request of the client
        :type request: bytes
        :return: url found in the request
        :rtype: str
        """
        decoded_request = request.decode("utf-8")
        first_line = decoded_request.split('\n')[0]
        url = first_line.split(' ')[1]
        return url

    @staticmethod
    def separate_url_and_prefix(url, prefix):
        """
        Separate the domain and path from a url.

        :param url: an unseparated url
        :param prefix: prefix to remove from the url
        :return: domain and path
        :rtype: str, str
        """
        temp = url
        if temp.startswith(prefix):
            temp = temp[len(prefix):]
        if temp.startswith('/'):
            temp = temp[1:]
        # location of http in the url
        http_location = temp.find("http://")
        if http_location != -1:
            temp = temp[http_location + 7:]
        # The slash after the domain
        after_slash = temp.find('/')
        if after_slash != -1:
            return temp[:after_slash], temp[after_slash:]
        else:
            return temp, '/'

    @staticmethod
    def prepare_request(request, address, path):
        """
        Prepare the request by replacing url in the first line with the path
        of the url, replace Host: <localaddress> with domain.

        :param request: request of the client
        :param address: external address to connect to
        :param path: what to retrieve from address
        :type request: bytes
        :type address: str
        :type path: str
        :return: prepared request
        :rtype: bytes
        """
        rewritten_url = False
        rewritten_host = False
        decoded_request = request.decode("utf-8")
        new_request = ""
        for line in decoded_request.split("\r\n"):
            if not rewritten_url:
                first_line = line.split(' ')
                # First line structured as {GET, POST} domain protocol
                new_request = \
                    "{} {} {}".format(first_line[0], path, first_line[2])
                rewritten_url = True
            elif not rewritten_host and line.startswith("Host:"):
                new_request += "\r\nHost: {}".format(address)
                rewritten_host = True
            else:
                new_request += "\r\n{}".format(line)
        return str.encode(new_request)


if __name__ == "__main__":
    p = Proxy(HOST, PORT, prefix=PREFIX, debug_level=2)
    p.run()
