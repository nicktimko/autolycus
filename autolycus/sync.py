from __future__ import absolute_import, print_function

import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description='')

    parser.add_argument('-r', '--repo')

    args = parser.parse_args()

if __name__ == '__main__':
    sys.exit(main())
