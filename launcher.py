import asyncio
import src.webster
import sys

def main():
    if len(sys.argv) == 1:
        asyncio.run(src.webster.word_of_the_day_search())
    elif len(sys.argv) == 2:
        asyncio.run(src.webster.search(sys.argv[1]))
    else:
        print('Error: Too many arguments provided.')

if __name__ == '__main__':
    sys.exit(main())