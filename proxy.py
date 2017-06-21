import socket
import argparse


class Proxy:
    def __init__(self, host, port, prefix="", max_connections=5,
                 request_size_limit=4096, reuseaddr=True, verbosity=0):
        """
        Initialize a new Proxy class.

        :param host: address to bind the proxy server to
        :param port: port to bind the proxy server to
        :param prefix: only accept proxy requests containing this prefix
        :param max_connections: max connections the proxy can have at a time
        :param request_size_limit: how much to read from a socket
        :param reuseaddr: whether to reuse and address if it is occupied
        :param verbosity: -1 no messages, 0 regular messages,
            1 connection messages, 2 socket messages
        :type host: str
        :type port: int
        :type prefix: str
        :type max_connections: int
        :type request_size_limit: int
        :type reuseaddr: bool
        :type verbosity: int
        """
        self.host = host
        self.port = port
        self.prefix = prefix
        self.max_connections = max_connections
        self.request_size_limit = request_size_limit
        self.reuseaddr = reuseaddr
        self.verbosity = verbosity
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
            if self.verbosity >= 0:
                print("Binding to {}:{}".format(self.host, self.port))
            self.server_socket = \
                socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Set option to reuse address on bind
            if self.reuseaddr:
                self.server_socket.setsockopt(
                    socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
        except socket.error:
            if self.verbosity >= 0:
                print("Unable to bind to {}:{}, exiting.".format(self.host,
                                                                 self.port))
            exit(1)

    def _listen(self):
        """
        Setup up server socket to listen for incoming connections.
        """
        try:
            self.server_socket.listen(self.max_connections)
        except socket.error:
            if self.verbosity >= 0:
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
                if self.verbosity >= 1:
                    print("New client from: {}".format(client_address))
                self.client_request(client_socket, client_address)
                client_socket.close()
            except KeyboardInterrupt:
                if self.verbosity >= 1:
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
        remote_connect_socket.settimeout(2)
        remote_connect_socket.connect((remote_address, remote_port))
        remote_connect_socket.sendall(request)
        try:
            while True:
                if self.verbosity >= 2:
                    print("Received data from ('{}' , {})".format(
                            remote_address, remote_port))
                read = remote_connect_socket.recv(self.request_size_limit)
                if len(read) == 0:
                    break
                if self.verbosity >= 2:
                    print("Sending data to {}".format(client_address))
                client_socket.send(read)
            remote_connect_socket.close()
        except socket.error as e:
            err = e.args[0]
            # Connection has read all the data
            if err == "timed out":
                remote_connect_socket.close()
            else:
                if self.verbosity >= 1:
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
        :type url: str
        :type prefix: str
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
        of the url, replace Host: <localaddress> with Host: <address>.

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
                # First line structured as {GET, POST} address protocol
                new_request = \
                    "{} {} {}".format(first_line[0], path, first_line[2])
                rewritten_url = True
            elif not rewritten_host and line.startswith("Host:"):
                new_request += "\r\nHost: {}".format(address)
                rewritten_host = True
            else:
                new_request += "\r\n{}".format(line)
        return str.encode(new_request)


def main():
    description = "Run a simple HTTP proxy server."
    parser = argparse.ArgumentParser(description=description)
    address_help = "Address to bind to. [Default: localhost]"
    port_help = "Port to bind to. [Default: 8000]"
    prefix_help = "Prefix to look for. [Default: /proxy/]"
    max_conn_help = "Max number of client connections at a time. [Default: 5]"
    size_limit_help = "Max size a network socket can read. [Default: 4096]"
    verbosity_help = "-1 off, 0 normal, 1 connection messages, 2 socket " \
                     "messages. [Default: 0]"
    parser.add_argument("-a", "--address", help=address_help,
                        default="localhost")
    parser.add_argument("-f", "--prefix", type=str, help=prefix_help,
                        default="/proxy/")
    parser.add_argument("-m", "--max_connections", type=int,
                        help=max_conn_help,
                        default=5)
    parser.add_argument("-p", "--port", type=int, help=port_help, default=8000)
    parser.add_argument("-s", "--size_limit", type=int, help=size_limit_help,
                        default=4096)
    parser.add_argument("-v", "--verbosity", type=int, help=verbosity_help,
                        default=0)
    args = parser.parse_args()
    address = args.address
    port = args.port
    prefix = args.prefix
    max_connections = args.max_connections
    size_limit = args.size_limit
    verbosity = args.verbosity
    proxy = Proxy(address, port, prefix, max_connections, size_limit,
                  verbosity=verbosity)
    proxy.run()

if __name__ == "__main__":
    main()
