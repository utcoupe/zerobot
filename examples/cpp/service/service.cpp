
#include <iostream>
#include <string>

#include "json/json.h"
#include "zhelpers.hpp"
#include "../../../services/cpp/service.hpp"

using namespace std;

class Cool : public Service
{
	public:
		Cool(const string & identity, const string & addr, CONNECTION_TYPE type=CONNECT)
			: Service(identity, addr, type) {};
	
	protected:
		virtual void process_request(const string & remote_id, const Json::Value & request) {
			Json::Value response;
			response["uid"] = request["uid"];
			if (request["fct"] == "ping") {
				response["data"] = request["args"][0].asInt() + 3;
				response["error"] = "";
				s_sendmore(_socket, remote_id);
			}
			else {
				response["data"] = "";
				response["error"]["error"] = "unknown function";
				response["error"]["tb"] = "";
			}
			string packed_response = _writer.write( response );
			s_send(_socket, packed_response);
		}

};

int main() {

	Cool cool("cool", "tcp://localhost:8081", Service::CONNECT);
	cout << "connect on port 8081" << endl;
	
	while (!s_interrupted) {
		cool.read();
	}

	return 0;
}


