"""External sockets denied before SDK imports; loopback permits Windows asyncio."""
import sys


def deny_outbound():
    def audit(event, args):
        if event in ("socket.connect", "socket.sendto", "socket.sendmsg"):
            address = args[1]
            if isinstance(address, str):  # Local Unix-domain socket.
                return
        elif event in ("socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr"):
            address = (args[0],)
        else:
            return
        if isinstance(address, tuple) and address[0] in ("localhost", "127.0.0.1", "::1"):
            return
        raise RuntimeError("offline test blocked outbound network")

    sys.addaudithook(audit)
