#!/usr/bin/python3
# Converts standard amounts to Minecraft stack (64) format

def convert_string(string: str) -> str:
    ret = ""
    num = ""
    while num is not None:
        num = None
        for i, char in enumerate(string):
            if char.isdigit():
                if num is None:
                    num = char
                else:
                    num += char
                if i + 1 == len(string):
                    ret += string[:-(len(string) - i + len(num))] + str(int(int(num) / 64)) + " | " + str(int(num) % 64)
                    num = None
            elif num is not None:
                ret += string[:-(len(string) - i + len(num))] + str(int(int(num) / 64)) + " | " + str(int(num) % 64)
                string = string[i:]
                break

def main():
    import sys
    
    args = sys.argv
    args.pop(0)

    if len(args) == 1:
        string = args[0]
    elif len(args) == 2:
        if args[1] == "-c":
            import os
            os.system("clear")
        else:
            print("Invalid argument. Must be one of the following: -c")
            exit()

        string = args[0]
    else:
        print("Invalid input. Must be [n2s <String to convert> <Optional argument>].")
        exit()
    
    print(convert_string(string))

if __name__ == "__main__":
    main()
