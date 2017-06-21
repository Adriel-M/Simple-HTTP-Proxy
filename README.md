Simple HTTP Proxy
===
A simple HTTP proxy written in python.

Usage
---
```
$ python proxy.py
usage: proxy.py [-h] [-a ADDRESS] [-f PREFIX] [-m MAX_CONNECTIONS] [-p PORT]
                [-s SIZE_LIMIT] [-v VERBOSITY]

Run a simple HTTP proxy server.

optional arguments:
  -h, --help            show this help message and exit
  -a ADDRESS, --address ADDRESS
                        Address to bind to. [Default: ] (all interfaces)
  -f PREFIX, --prefix PREFIX
                        Prefix to look for. [Default: /proxy/]
  -m MAX_CONNECTIONS, --max_connections MAX_CONNECTIONS
                        Max number of client connections at a time. [Default:
                        5]
  -p PORT, --port PORT  Port to bind to. [Default: 8000]
  -s SIZE_LIMIT, --size_limit SIZE_LIMIT
                        Max size a network socket can read. [Default: 4096]
  -v VERBOSITY, --verbosity VERBOSITY
                        -1 off, 0 normal, 1 connection messages, 2 socket
                        messages. [Default: 0]

```

