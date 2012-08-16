

var client = require('./client').Client("remote_cool_nodejs", "tcp://localhost:8080", "cool");
var n_recv = 0,
	N = 10000,
	start = 0;
client.on_message = function() {
	++n_recv;
	if (n_recv == N) {
		ellapsed = new Date().getTime() - start;
		average = ellapsed / N;
		reqs_s = N / (ellapsed / 1000.0);
		console.log("ellapsed", ellapsed, "ms");
		console.log("average", average, "ms");
		console.log("reqs/s", reqs_s);
	}
};
	
start = new Date().getTime();
for (var i=0; i< N; ++i) {
	client.remote_call('ping', [56,], {});
}

