import argparse
import json
import random
import selectors
import socket
import struct
from types import SimpleNamespace
from squares import Game

SEL = selectors.DefaultSelector()


def pack_color(rgb):
    return struct.pack("!3B", *rgb)


def wrapped_send(sock: socket.socket, data, msg):
    # Write to socket, and if get a full buffer error, tell the selector to care about writing
    try:
        left_to_send = msg
        while len(left_to_send) > 0:
            sent = sock.send(left_to_send)
            left_to_send = left_to_send[sent:]
    except socket.error as e:
        # EAGAIN and EWOULDBLOCK are basically the same error but for different systems/legacy architecture
        if e.args[0] == socket.EAGAIN or e.args[0] == socket.EWOULDBLOCK:
            data.outb += left_to_send
            SEL.unregister(sock)
            SEL.register(sock, selectors.EVENT_READ | selectors.EVENT_WRITE, data=data)
        else:
            raise e


def recv_single_as_int(sock: socket.socket):
    byte = sock.recv(1)
    if byte == b"":
        SEL.unregister(sock)
        sock.close()
        return None
    return int.from_bytes(byte, "little")


def send_to_all(message, orig_addr):
    socket_map = SEL.get_map()
    for conn in socket_map:
        loop_key = socket_map[conn]
        if loop_key.data is not None:  # not our listening socket
            loop_addr = loop_key.data.addr
            if loop_addr != orig_addr:
                wrapped_send(loop_key.fileobj, loop_key.data, message)


class Server_Game(Game):
    def __init__(self, size, goals):
        super().__init__(size)
        self.player_dict = {}
        self.squares = [set() for i in range(size * size)]
        self.goals = goals[: size * size]

    def mark(self, idx, player_id):
        if player_id in self.squares[idx]:
            self.squares[idx].remove(player_id)
        else:
            self.squares[idx].add(player_id)

    def new_player(self, player_id, player_color):
        message = b""
        if player_id in self.player_dict:
            old_color = pack_color(self.player_dict[player_id])
            new_color = pack_color(player_color)
            for i in range(len(self.squares)):
                if player_id in self.squares[i]:
                    # transmit mark to current players to unmark old color and mark new color
                    idx_byte = i.to_bytes(1, "little")
                    message += idx_byte + old_color + idx_byte + new_color
        self.player_dict[player_id] = player_color
        return message

    def pack_goals(self):
        return struct.pack("!%iB" % (self.size * self.size), *(self.goals))

    def pack_player(self, player_id):
        return pack_color(self.player_dict[player_id])

    def pack_square(self, idx):
        ret = len(self.squares[idx]).to_bytes(1, "little")
        for player_id in self.squares[idx]:
            ret += self.pack_player(player_id)
        return ret

    def pack_board(self):
        ret = b""
        for i in range(self.size * self.size):
            ret += self.pack_square(i)
        return ret

    def new_connection(self, sock):
        conn, (host, port) = sock.accept()
        conn.setblocking(True)
        print(f"Accepted connection from {host}")
        replacement_msg = None
        if (spectate := recv_single_as_int(conn)) is None:
            return
        elif not spectate:
            if (r := recv_single_as_int(conn)) is None:
                return
            if (g := recv_single_as_int(conn)) is None:
                return
            if (b := recv_single_as_int(conn)) is None:
                return
            replacement_msg = self.new_player(host, (r, g, b))
        data = SimpleNamespace(addr=host, outb=b"")
        wrapped_send(conn, data, self.size.to_bytes(1, "little") + self.pack_goals() + self.pack_board())
        conn.setblocking(False)
        if replacement_msg:
            send_to_all(replacement_msg, host)
        SEL.register(conn, selectors.EVENT_READ, data=data)

    def read(self, key: selectors.SelectorKey):
        sock = key.fileobj
        data = key.data
        idx = sock.recv(1)
        if idx:
            self.mark(int.from_bytes(idx, "little"), data.addr)
            message = idx + struct.pack("!3B", *(self.player_dict[data.addr]))
            send_to_all(message, data.addr)
        else:
            SEL.unregister(sock)
            sock.close()

    @staticmethod
    def write(key: selectors.SelectorKey):
        # Alternative write, called with a selector key, for when we're actively selecting on writing availability
        # If we write our entire buff successfully, we can stop selecting on writing for this socket
        sock = key.fileobj
        data = key.data
        if data.outb:
            sent = sock.send(data.outb)
            data.outb = data.outb[sent:]
            if not data.outb:
                # We are freed from caring about writing
                SEL.unregister(sock)
                SEL.register(sock, selectors.EVENT_READ, data=data)


def parse(max_size):
    parser = argparse.ArgumentParser(description="Start a server session of a synced bingo game.")
    parser.add_argument("host", help="internal IP address of server")
    parser.add_argument("port", type=int, help="server port to connect to (make sure you forwarded it!)")
    parser.add_argument(
        "board_size",
        type=int,
        help="dimension of bingo board (min 2, max dependent on total amount of goals)",
        metavar="N",
        choices=range(2, max_size + 1),
    )
    parser.add_argument("-s", "--seed", type=int, help="random seed to use to generate board layout")
    return parser.parse_args()


def main():
    with open("./bingo.json") as f:
        # TODO strip comments
        goals = json.load(f)
        goal_list = sorted(
            [goals[key]["Desc"] for key in goals if isinstance(goals[key], dict) and goals[key].get("Desc")]
        )
        goal_indices = list(range(len(goal_list)))
    max_size = int(len(goal_list) ** 0.5)
    args = parse(max_size)
    server_addr = (args.host, args.port)
    board_size = args.board_size
    if args.seed is not None:
        seed = args.seed
    else:
        # this is the only way I can figure out how to generate a seed and print it to save
        seed = random.randint(0, 2**32)
    random.seed(seed)
    print("Generating board with seed ", str(seed))
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(server_addr)
    listener.listen()
    listener.setblocking(False)
    SEL.register(listener, selectors.EVENT_READ, data=None)
    random.shuffle(goal_indices)

    game = Server_Game(board_size, goal_indices[: board_size * board_size])

    while True:
        try:
            # On Windows, timeout=None breaks KeyboardInterrupt for some reason
            events = SEL.select(timeout=10)
            for key, mask in events:
                if key.data is None:
                    # This is our listener socket, new connection
                    game.new_connection(key.fileobj)
                else:
                    if mask & selectors.EVENT_READ:
                        game.read(key)
                    if mask & selectors.EVENT_WRITE:
                        game.write(key)
        except KeyboardInterrupt:
            SEL.close()
            break
        except ConnectionResetError:
            # Server shouldn't crash if someone disconnects weirdly
            pass


if __name__ == "__main__":
    main()
