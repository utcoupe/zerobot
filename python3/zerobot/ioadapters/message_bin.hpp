#ifndef MESSAGE_BIN_H
#define MESSAGE_BIN_H

#include <stdlib.h>

#define MAX_ARGS	10 // nombre maximum d'arguments pour un appel de methode

int read_incomming_data(void (*call)(int16_t, int8_t, int8_t, int16_t[MAX_ARGS]), int max_read=100);
int send(int16_t uid, char type, int8_t nb_args, int16_t args[MAX_ARGS]);
int send_response(int16_t uid, int16_t nb_args, int16_t args[MAX_ARGS]);
int send_event(int16_t uid, int16_t nb_args, int16_t args[MAX_ARGS]);

#ifndef ARDUINO

#include <stdio.h>
#include <iostream>
using namespace std;

class _Serial {
	public:
		_Serial() : _available(0) {};
		int readBytes(char * buffer, int length) {
			for (int i=0; i<length; ++i) {
				buffer[i] = read();
			}
			return length;
		};
		int available() {
			_available += rand() % 10;
			return _available;
		};
		int read() {
			_available -= 1;
			return getchar();
		};
		int write(char v) {
			putchar(v);
			return 1;
		};
		int write(char * buff, int len) {
			for (char * c=buff; c<buff+len; ++c) {
				putchar(*c);
			}
			return len;
		};

	private:
		int _available;
};
static _Serial Serial;

#endif

#endif

