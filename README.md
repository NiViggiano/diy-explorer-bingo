# DIY Exploration Bingo
## Or: I Can't Believe It's Not BingoSync!

A server and client to host synced games of [video game] bingo, specifically made with the Exploration format in mind. Written in pure Python, with all the GUI made by everyone's favorite module Tkinter, so that no additional Python modules need to be installed.

Based on, and meant to work with, [BingoSync by kbuzsaki](https://github.com/kbuzsaki/bingosync), the most widely-used synced bingo board site but which is limited to 5x5 always-visible squares (and whose backend I could not figure out enough to pull request), as well as [hk-exploration-bingo by Butchie1331](https://github.com/Butchie1331/hk-exploration-bingo), which provided the rules and setup of Exploration but only for a single player.

## Usage
* Download [Python 3.9+](https://www.python.org/downloads/) and make sure to check "Add Python to PATH".
* Put the files from this repository into a single directory. Also put a file named "bingo.json" into this directory; the file should be [a generator from the BingoSync generator directory](https://github.com/kbuzsaki/bingosync/tree/master/bingosync-app/generators), but only containing the `bingoList` itself (i.e. delete everything besides the right-hand-side of "`var bingoList`").
* **IMPORTANT**: currently only works with generators that use the "synerGen" base generator, e.g. Hollow Knight, Pikmin 2, Plasmophobia, etc. Also, currently, the file needs to not have any comments inside of it. A future update will solve these two issues.


### Server
* To run the server, you will need to set up port forwarding on your router. The exact way to do this varies by router brand, but since it's also required for Minecraft servers there are plenty of easy-to-follow guides.
* In a terminal, run `python <filepath>/explorer-server.py -h`; if this doesn't work, the command may be either `python3` or `py`. 
* You will receive an explanation of the current command line arguments accepted. Currently, `python explorer-server.py <internal IP> <internal port> <board size>` are the required arguments, with options to input a seed to use to generate the board.

### Client
* In a terminal, run `python <filepath>/explorer-client.py -h`; if this doesn't work, the command may be either `python3` or `py`. 
* You will receive an explanation of the current command line arguments accepted. Currently, `python explorer-server.py <public server IP> <public server port>` are the required arguments, with options for screen resolution, player color, spectate mode, and verbose mode.
