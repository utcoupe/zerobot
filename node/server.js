
try {
	var zmq = require('zmq');
}
catch (Exception) {
	var zmq = require('./zmq/lib/index.js');
}

function createServer(frontPort, backPort, pubPort) {
	var frontSocket = zmq.socket('router'),
		backSocket = zmq.socket('router'),
		pubSocket = zmq.socket('pub');

	frontSocket.identity = 'ft-' + process.pid;
	backSocket.identity = 'bc-' + process.pid;
	pubSocket.identity = 'pb-' + process.pid;
	
	frontSocket.bind(frontPort, function (err) {
		console.log('bound', frontPort);
	});
	
	frontSocket.on('message', function() {
		pubSocket.send(Array.prototype.slice.call(arguments));
		//pass to back
		tmp = arguments[0];
		arguments[0] = arguments[1];
		arguments[1] = tmp;
		backSocket.send(Array.prototype.slice.call(arguments));
	});

	backSocket.bind(backPort, function (err) {
		console.log('bound', backPort);
	});
	
	backSocket.on('message', function() {
		pubSocket.send(Array.prototype.slice.call(arguments));
		//pass to front
		tmp = arguments[0];
		arguments[0] = arguments[1];
		arguments[1] = tmp;
		frontSocket.send(Array.prototype.slice.call(arguments));
	});

	pubSocket.bind(pubPort, function(err) {
		console.log('bound', pubPort);
	});
}

exports.createServer = createServer;

