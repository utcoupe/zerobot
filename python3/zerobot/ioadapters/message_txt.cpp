#if defined(ARDUINO) && ARDUINO >= 100
#	include "Arduino.h"
#elif defined(ARDUINO)
#	include "WProgram.h"
#	include "wiring.h"
#endif

#include "message.hpp"




///
/// Parse les donnees recues sur le port serie et appel la fonction cmd pour effectuer les traitements
///
int readIncomingData(void (*call)(int16_t, int8_t, int8_t, int16_t[MAX_ARGS]), int max_read)
{
	static char currentArg[10]; //<= cedric : je reduis ici pour menager la memoire des arduino (vu qu'on les cast en entier avec atoi, le max c'est 6 normalement (-32000 -> +32000)
	static int16_t args[MAX_ARGS+2]; // uid + id_cmd + args*MAX_ARGS
	static int argsIndex = 0;
	static int currentArgIndex = 0;
	int r = 0;

	/*
	 * A propos du protocole :
	 * id_cmd:arg1:arg2:...
	 * - un message se termine par \n
	 */

	// s'il y a des donnees a lire
	int available = Serial.available();
	if (available > max_read) {
		available = max_read;
	}
	for(int i = 0; i < available; i++) {
		// recuperer l'octet courant
		int data = Serial.read();
		++r;
		switch(data){
			// separateur
			case SEP:
			{
			   	currentArg[currentArgIndex] = '\0';
	   			args[argsIndex] = atoi(currentArg);
				argsIndex++;
				currentArgIndex = 0;
				break;
			}
			// fin de trame
			case '\n':
			{
				currentArg[currentArgIndex] = '\0';
				args[argsIndex] = atoi(currentArg);
				call(args[0],args[1],argsIndex-1,args+2); // id_cmd, *args, sizeArgs
  				argsIndex = 0;
				currentArgIndex = 0;
				break;
			}
			default:
			{
				currentArg[currentArgIndex] = data;	
				currentArgIndex++;
				break;
			}
		}
	}

	return r;
}


int send(int16_t uid, char type, int8_t nb_args, int16_t args[MAX_ARGS]) {
	int r=0;
	r+=Serial.print(uid); r+=Serial.print(SEP);
	r+=Serial.print((int)type); r+=Serial.print(SEP);
	for (int16_t * a=args; a<args+nb_args; ++a) {
		r+=Serial.print(*a); r+=Serial.print(SEP);
	}
	r+=Serial.print('\n');
	return r;
}

int sendResponse(int16_t uid, int16_t nb_args, int16_t args[MAX_ARGS]) {
	return send(uid, 1, nb_args, args);
}

int sendEvent(int16_t uid, int16_t nb_args, int16_t args[MAX_ARGS]) {
	return send(uid, 0, nb_args, args);
}

int send(int16_t uid, char type, char * s) {
	int r=0;
	r+=Serial.print(uid); r+=Serial.print(SEP);
	r+=Serial.print((int)type); r+=Serial.print(SEP);
	r+=Serial.println(s);
	return r;
}

int sendResponse(int16_t uid, char * s) {
	return send(uid, 1, s);
}
int sendEvent(int16_t uid, char * s) {
	return send(uid, 0, s);
}


