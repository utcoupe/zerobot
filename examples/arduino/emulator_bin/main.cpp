#include <iostream>
#include <time.h>

using namespace std;


#include "message_bin.hpp"


void acall(int16_t uid, int8_t id_cmd, int8_t nb_args, int16_t args[MAX_ARGS]) {
	cerr << endl;
	cerr << "FULL MESSAGE" << endl;
	cerr << "============" << endl;
	cerr << "uuid:\t" << uid << endl;
	cerr << "id_cmd:\t" << (int)id_cmd << endl;
	cerr << "nb_args:\t" << (int)nb_args << endl;
	for (int i=0; i<nb_args; ++i)
		cerr << "\targ" << i << ":\t" << args[i] << endl;

	send_response(uid, nb_args, args);
	cerr << "sent response" << endl;
	send_event(56, nb_args, args);
	cerr << "sent event" << endl;
}



int main() {
	srand ( time(NULL) );

	int l=0;
	while (l < 20) {
		l += read_incomming_data(acall, 5);
	}

	return 0;
}


