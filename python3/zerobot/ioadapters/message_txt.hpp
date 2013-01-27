#ifndef MESSAGE_TXT_H_
#define MESSAGE_TXT_H_

#define SEP			'+'
#define SERIAL_BAUD 115200
#define MAX_ARGS	10

#include <stdlib.h>

void initSerialLink();
int readIncomingData(void (*call)(int16_t, int8_t, int8_t, int16_t[MAX_ARGS]), int max_read=10);
int send(int16_t uid, char type, int8_t nb_args, int16_t args[MAX_ARGS]);
int sendResponse(int16_t uid, int16_t nb_args, int16_t args[MAX_ARGS]);
int sendEvent(int16_t uid, int16_t nb_args, int16_t args[MAX_ARGS]);
int send(int16_t uid, char type, char * s);
int sendResponse(int16_t uid, char * s);
int sendEvent(int16_t uid, char * s);


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
		void begin(int baudrate) {};
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
		int print(char v) {
			cout << v;
			return 1;
		};
		int println(char v) {
			cout << v << endl;
			return 1;
		};
		int print(int i) {
			cout << i;
			return 42;
		};
		int println(int i) {
			cout << i << endl;
			return 42;
		};
		int print(char * s) {
			cout << s;
			return 42;
		}
		int println(char * s) {
			cout << s << endl;
			return 42;
		}

	private:
		int _available;
};
static _Serial Serial;

#endif


#endif /* MESSAGE_H_ */
