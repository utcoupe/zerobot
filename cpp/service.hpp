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


	protected:
		virtual void process_request(const string & remote_id, const Json::Value & request) = 0;
		
		string _identity;
		string _addr;
		Json::Reader _reader;
		Json::StyledWriter _writer;
		zmq::context_t _context;
		zmq::socket_t _socket;

};


