#include "zhelpers.hpp"

using namespace std;

class Service
{
	public:
		enum CONNECTION_TYPE {BIND,CONNECT};
		Service(const string & identity, const string & addr, CONNECTION_TYPE type=CONNECT)
			: _identity(identity), _addr(addr), _context(1), _socket(_context, ZMQ_DEALER)
			{
				_socket.setsockopt( ZMQ_IDENTITY, identity.c_str(), identity.length());
				switch (type) {
					case CONNECT:
						_socket.connect(addr.c_str());
					break;
					case BIND:
						_socket.bind(addr.c_str());
					break;
				}
					
			};

		void read() {
			Json::Value request;
			string remote_id = s_recv(_socket);
			string msg = s_recv(_socket);
			//cout << remote_id << " " << msg << endl;
			bool parsingSuccessful = _reader.parse( msg, request );
			if ( !parsingSuccessful ) {
				cerr  << "Failed to parse request : " << _reader.getFormattedErrorMessages();
				return;
			}
			//cout << request << endl;
			process_request(remote_id, request);
		};


		/**
		 * Renvoie une réponse au client
		 */
		void sendResponse(const string & remote_id, const Json::Value & request, Json::Value & data) {
			Json::Value response;
			Json::Value null_value;
			response["uid"] = request["uid"];
			response["error"] = null_value;
			response["data"] = data;
			string packed_response = _writer.write( response );
            s_sendmore(_socket,  remote_id);
			s_send(_socket, packed_response);
		};
		
		/**
		 * Renvoie une erreur au client
		 */
		void sendError(const string & remote_id, const Json::Value & request, const string error, const string traceback) {
			Json::Value response;
			response["uid"] = request["uid"];
			response["error"]["error"] = error;
			response["error"]["tb"] = traceback;
			response["data"] = "";
			string packed_response = _writer.write( response );
            s_sendmore(_socket,  remote_id);
			s_send(_socket, packed_response);
		}

	protected:
		virtual void process_request(const string & remote_id, const Json::Value & request) = 0;
		
		string _identity;
		string _addr;
		Json::Reader _reader;
		Json::StyledWriter _writer;
		zmq::context_t _context;
		zmq::socket_t _socket;

};


