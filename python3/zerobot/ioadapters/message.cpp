#if defined(ARDUINO) && ARDUINO >= 100
#	include "Arduino.h"
#elif defined(ARDUINO)
#	include "WProgram.h"
#	include "wiring.h"
#else


#include <stdio.h>
#include <stdlib.h>
#include <time.h>
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
_Serial Serial = _Serial();
#endif


#define MAX_ARGS	10 // nombre maximum d'arguments pour un appel de methode
#define LEN_uid		2  // uid = 2 char


/**
		name   | size(bits) |  start   |  end  
	===========|============|==========|=======
	 uid       |     16     |     0    |   16
	 id_cmd    |      8     |    16    |   24
	 nb_args   |      8     |    24    |   32
	 arg0      |     16     |    32    |   48
	 arg1      |     16     |    48    |   64
	 ..        |     ..     |    ..    |   ..
	 argN      |     16     | 32+16*N  | 32+16*(N+1)
 *
 * Renvoie le nombre d'octes lus
 */
int read_incomming_data(void (*call)(int16_t, int8_t, int8_t, int16_t[MAX_ARGS]), int max_read=100) {
	static char state=0;           // 0:uid  1=id_cmd  2=nb_args  3==args
	static int16_t uid;            // uid (16 bits)
	static char * puid = (char*)&uid; // version char[2] de uid
	static int id_puid=0;          // id dans le tableau puid
	static int8_t id_cmd=-1;       // id de la commande (8 bits)
	static int8_t nb_args=-1;      // nombre d'arguments (8 bits)
	static int16_t args[MAX_ARGS]; // les arguments (chacun sur 16 bits)
	static int id_arg=0;           // id dans le tableau args
	static int nb_empty=0;         // nb de carateres vides successifs
	char * buffer;                 // buffer
	int r = 0;                     // retour de la fonction

	int to_read = Serial.available();     // recuperation du nombre d'octet qu'on peu lire
	if (max_read < to_read)               // limitation du nombre d'octets lus en une foi
		to_read = max_read;
	if (to_read < 2)
		to_read = 2;
	
	cerr << "to_read " << to_read << endl;
	
	while (to_read > 0) {
		switch (state) {
			case 0:                // remplissage de uid
				if (to_read > 1) {
					buffer = (char*)&uid;
					Serial.readBytes(buffer, 2);
					to_read -= 2; r += 2;
					state = 1;
					cerr << "uid " << uid << endl;
				}
				else {
					to_read = 0;   // exit
				}
				break;
			
			case 1:                // remplissage de id_cmd
				state = 1;
				id_cmd = Serial.read();
				--to_read; ++r;
				cerr << "id_cmd " << (int)id_cmd << endl;
				state = 2;
				break;

			case 2:                // remplissage de nb_args
				state = 2;
				nb_args = Serial.read();
				--to_read; ++r;
				nb_args %= (MAX_ARGS+1);
				if (nb_args < 0) nb_args += MAX_ARGS+1;
				cerr << "nb args " << (int)nb_args << endl;
				state = 3;
				break;

			case 3:                // remplissage des arguments
				if (to_read > 1) {
					buffer = (char*)(args+id_arg);
					Serial.readBytes(buffer, 2);
					to_read -= 2; r += 2;
					cerr << "arg " << id_arg << " " << args[id_arg] << endl;
					++id_arg;
				}
				else {
					to_read = 0;   // exit
				}
				break;

			default:               // neverland
				cerr << "WTF don't be here !" << endl;
				break;
		}


		// si on a lu une trame entiere (uid + id_cmd + nb_args + args)
		// alors on appel 'call' puis on reset tout
		if (state==3 and id_arg==nb_args) {
			call(uid, id_cmd, nb_args, args);
			id_arg = 0;
			state = 0;
		}
	}

	return r;
}

int send(int16_t uid, char type, int8_t nb_args, int16_t args[MAX_ARGS]) {
	int r = 0;
	r += Serial.write((char*)(&uid), 2);
	r += Serial.write(type);
	r += Serial.write((char)nb_args);
	r += Serial.write((char*)args, 2*nb_args);
	return r;
}

int send_response(int16_t uid, int16_t nb_args, int16_t args[MAX_ARGS]) {
	return send(uid, 1, nb_args, args);
}

int send_event(int16_t uid, int16_t nb_args, int16_t args[MAX_ARGS]) {
	return send(uid, 0, nb_args, args);
}



