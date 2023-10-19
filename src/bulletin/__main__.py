import sys
import argparse
import bulletin

parser = argparse.ArgumentParser(description='Bulletin', prog='bulletin')
parser.add_argument('server', type=str, help='p2p or relay')
parser.add_argument('--host', type=str, help='host to listen on', default='0.0.0.0')
parser.add_argument('--port', type=int, help='port to listen on', default=12345)

args = parser.parse_args()

if args.server == 'p2p':
    bulletin.P2PServer(args.host, args.port).run()
elif args.server == 'relay':
    bulletin.RelayServer(args.host, args.port).run()
else:
    print("Invalid server type (use 'p2p' or 'relay')")
    sys.exit(1)

