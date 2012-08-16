

var uuid = require('node-uuid');
try {
	var zmq = require('zmq');
}
catch (Exception) {
	var zmq = require('./zmq/lib/index.js');
}


var Client = function(identity, conn_addr, remote_id) {
	var self = this;
	this.identity = identity;
	this.remote_id = remote_id;
	var socket = zmq.socket('dealer');
	socket.setsockopt('identity', new Buffer(identity));
	socket.on("message", function() {
		self.on_message();
	});
	socket.connect(conn_addr);
	this.socket = socket;
	this.cb = {};
}

Client.prototype.on_message = function() {
	console.log("Received");
	for (var i=0; i<arguments.length; i++) {
		console.log(''+i+' : '+arguments[i].toString());
	}
	//response = JSON.parse(arguments[1].toString());
	//console.log(response);
}

Client.prototype.uid = function() {
	return uuid();
}

Client.prototype.remote_call = function(fct, args, kwargs, uid) {
	if (uid == undefined) uid = this.uid();
	this.socket.send([this.remote_id, JSON.stringify({uid: uid, fct: fct, args: args, kwargs: kwargs})])
}

exports.Client = function(identity, conn_addr, remote_id) {
	return new Client(identity, conn_addr, remote_id);
}

