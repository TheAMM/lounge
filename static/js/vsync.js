/*
/ Websockets, man
*/

// I just love "Hello {0}".format("World!") -type string formatting
if (!String.prototype.format) {
  String.prototype.format = function() {
    var args = arguments;
    return this.replace(/{(\d+)}/g, function(match, number) { 
      return typeof args[number] != 'undefined' ? args[number] : match;
    });
  };
}


var WebSocketClient = function () {
	if (!("WebSocket" in window)) {
		console.log("No support for WebSocket!")
	}
	this.list = null;
	this.sock = null;
	this.uuid = this.generateUUID(6)
	this.client = null;
	this.listeners = {}
};
WebSocketClient.prototype.addListener = function (name, func) {
	if (name in this.listeners) {
		this.listeners.push(func)
	} else {
		this.listeners[name] = [func]
	}
}
WebSocketClient.prototype.removeListener = function (name, func) {
	if (name in this.listeners) {
		var ind = this.listeners[name].indexOf(func)
		if (ind != -1) {
			this.listeners[name].splice(ind, 1);
		}
	}
}

WebSocketClient.prototype.generateUUID = function (length) {
	length = length || 6
	r = Math.random()
	baseN = function (number, b, numerals) {
		b = b || 62;
		numerals = numerals || "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
		if (number == 0) {
			return numerals[0];
		} else {
			var tmp = baseN(Math.floor(number / b), b, numerals).replace(new RegExp("^" + numerals[0] + "+$"), '')
			tmp += numerals[number % b];
			return tmp
		}
	}
	return baseN( Math.floor(r*Math.pow(62, length)), 62)
}

WebSocketClient.prototype.processMessage = function (data) {
	var j = JSON.parse(data)
	if ("type" in j) {
		var name = j["type"]
		if (name in this.listeners) {
			var arr = this.listeners[name]
			for (var i = 0; i < arr.length; i++) {
				arr[i]({type:name, json:j, wsc:this})
			};
		}

		if (this.client) {
			for (var attr in this.client) {
				if (attr.toLowerCase() === "on"+name.toLowerCase()) {
					this.client[attr](j, this);
					break;
				}
			}
		}
		// var ce = new CustomEvent(j["type"], { 'detail': {'data':j, 'wsc':this} });
		// this.dispatchEvent(ce)
	}
	// console.log(j)
}
WebSocketClient.prototype.rawSend = function (data) {
	console.log("Sending:  ", data)
	this.sock.send(data)
}
WebSocketClient.prototype.sendMessage = function (jsonData) {
	this.rawSend(JSON.stringify(jsonData));
}
WebSocketClient.prototype.connect = function (uri) {
	// this.sock = new WebSocket("ws://0x40hu.es:8088/")
	// console.log("Creating...")
	this.sock = new WebSocket(uri)
	// console.log("Socket created!")
	var that = this;
	this.sock.onopen = function(e) { that.socketOnOpen(e, that); }
	this.sock.onmessage = function(e) { that.socketOnMessage(e, that); }
	this.sock.onclose = function(e) { that.socketOnClose(e, that); }
}
WebSocketClient.prototype.socketOnOpen = function (e, that) {
	console.log("Socket open!");

	that.sendMessage({type:"identify", uuid:that.uuid});
}
WebSocketClient.prototype.socketOnClose = function (e, that) {
	console.log("Socket closed!")
}
WebSocketClient.prototype.socketOnMessage = function (e, that) {
	console.log("Receiving:", e.data)
	that.processMessage(e.data)
}



// function processMessage(m) {
// 	l.innerHTML += "<br><span style='color:blue'>&lt;&lt; " + m + "</span>"

// 	if (!master) {
// 		var sp = m.split(" ", 2)
// 		switch (sp[0]) {
// 			case "play":
// 			case "pause":
// 				var timeDelta = parseFloat(sp[1]) - v.currentTime
// 				if (Math.abs(timeDelta) > 0.5) {
// 					v.currentTime = parseFloat(sp[1])
// 				}
// 				if (sp[0] == "play") { v.play()  }
// 				else 				 { v.pause() }
// 				break
// 		}
// 	}
// }

// function sendEvent(e) {
// 	switch(e.type) {
// 		case "play":
// 			send(e.type + " " + v.currentTime)
// 			break
// 		case "pause":
// 			if (!v.seeking) {
// 				send(e.type + " " + v.currentTime)
// 			}
// 			break
// 		// case "seeked":
// 			// send(e.type + " to " + v.currentTime)
// 			// break
// 	}
// }

