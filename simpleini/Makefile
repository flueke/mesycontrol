.PHONY: all clean

all: main

clean:
	-rm *.o main

main: main.o ConvertUTF.o
	g++ -Wall -g main.o ConvertUTF.o -o main
