import argparse
import json
import random
import selectors
import socket
import struct
from squares import Game_Controller

SEL = selectors.DefaultSelector()


def recv_single_as_int(sock: socket.socket):
    byte = sock.recv(1)
    if byte == b"":
        SEL.unregister(sock)
        sock.close()
        return None
    return int.from_bytes(byte, "little")


class Socket_Game(Game_Controller):
    def __init__(
        self, board_size, color, goal_indices, goal_list, board_width, board_height, spectate=False, verbose=False
    ):
        super().__init__(board_size, color, goal_indices, goal_list, board_width, board_height, spectate)
        self.outb = b""
        self.delay = 100  # TODO hardcode this? put this elsewhere?
        self.verbose = verbose
        if spectate:
            self.root.unbind("<Button-1>")

    def run(self):
        self.check_for_updates()
        super().run()

    def mark_init_squares(self, sock):
        # assumes blocking
        for square_idx in range(self.size * self.size):
            num_markers = recv_single_as_int(sock)
            if num_markers is None:
                return False
            for player_idx in range(num_markers):
                rgb = []
                for color_idx in range(3):
                    color = recv_single_as_int(sock)
                    if color is None:
                        return False
                    rgb.append(color)
                self.mark(square_idx, tuple(rgb))
        return True

    def read_square(self, sock):
        # assumes non-blocking
        marked_square = b""
        while len(marked_square) < 4:
            marked_square += sock.recv(4)
            if marked_square == b"":
                return False
        idx = marked_square[0]
        (R, G, B) = struct.unpack_from("!3B", marked_square, 1)
        self.mark(idx, (R, G, B))
        if self.verbose:
            print("%i %i %i has marked %s" % (R, G, B, self.goal_list[self.goal_indices[idx]]))
        return True

    def write_square(self, sock):
        if self.outb:
            sent = sock.send(self.outb)
            self.outb = self.outb[sent:]

    def check_for_updates(self):
        events = SEL.select(timeout=1)
        if events:
            for (key, mask) in events:
                sock = key.fileobj
                if mask & selectors.EVENT_READ:
                    if not self.read_square(sock):
                        SEL.unregister(sock)
                        sock.close()
                        return
                if mask & selectors.EVENT_WRITE:
                    self.write_square(sock)
        self.root.after(self.delay, self.check_for_updates)

    def mouse_pressed(self, event):
        idx = super().mouse_pressed(event)
        if idx is not None:
            self.outb += idx.to_bytes(1, "little")


def parse():
    parser = argparse.ArgumentParser(description="Open a client session to a synced bingo server.")
    parser.add_argument("host", help="public IP address of server")
    parser.add_argument("port", type=int, help="server port to connect to (make sure they forwarded it!)")
    parser.add_argument("-r", "--resolution", nargs=2, type=int, help="size to make board (width then height)")
    parser.add_argument("-c", "--color", nargs=3, type=int, help="R G B value of color for player")
    parser.add_argument(
        "-s", "--spectate", action="store_true", help="set this flag if you want to spectate instead of play"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="set this flag to receive a message every time a goal is marked"
    )
    return parser.parse_args()


def main():
    args = parse()
    server_addr = (args.host, args.port)
    if args.resolution is not None:
        width, height = args.resolution
    else:
        width = 1600
        height = 1000
    if args.color is not None:
        R, G, B = args.color
    else:
        R = random.randint(0, 255)
        G = random.randint(0, 255)
        B = random.randint(0, 255)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Block until initial data is sent and received
    sock.connect(server_addr)
    # First tell the server if we're a player
    if args.spectate:
        sock.sendall((1).to_bytes(1, "little"))
    else:
        # We're a player, send our color so the server can deal with reconnection
        sock.sendall((0).to_bytes(1, "little"))
        sock.sendall(struct.pack("!3B", R, G, B))
    board_size = recv_single_as_int(sock)
    if board_size is None:
        return
    goal_indices = b""
    while len(goal_indices) < board_size * board_size:
        goal_indices += sock.recv(board_size * board_size - len(goal_indices))
    with open("./bingo.json") as f:
        # TODO strip comments
        goals = json.load(f)
        goal_list = sorted(
            [goals[key]["Desc"] for key in goals if isinstance(goals[key], dict) and goals[key].get("Desc")]
        )
    game = Socket_Game(board_size, (R, G, B), goal_indices, goal_list, width, height, args.spectate, args.verbose)
    if not game.mark_init_squares(sock):
        SEL.unregister(sock)
        sock.close()
        return
    sock.setblocking(False)
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    SEL.register(sock, events)
    game.run()


if __name__ == "__main__":
    main()
