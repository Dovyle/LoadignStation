const express = require('express');
const app = express();
const http = require('http');
const midApp = http.createServer(app);
const {Server} = require("socket.io");
const io = new Server(midApp);
const dgram = require('node:dgram');
const lowApp = dgram.createSocket('udp4');
const mysql = require('mysql2');


const connection = mysql.createConnection({
  host: '192.168.1.131',
  user: 'admin',
  password: 'nCrGu@rd!@n$',
  database: 'mydb',
  port: '3306'
});


app.get('/', (req, res) => {
    res.sendFile(__dirname + '/index.html');
});


app.use(express.static('public'));


let deviceAddress = "";
let appPort = "";
let tag_id = "";
let current_user = "";


const databaseConnection = async (tag_id, transaction_balance) => {
    return new Promise((resolve, reject) => {
        connection.connect(function(error) {
            if (error) {
                console.error('Error connecting to MySQL database:', error);
                reject(error);
            } else {
                console.log('Connected to MySQL database!');
                if (transaction_balance === 0) {

                    connection.query("SELECT id_number, first_name, middle_initial, last_name, balance, roles, number_of_passengers FROM users_server WHERE tag_uid = '" + tag_id + "'", async function (error, result, fields) {
                        if (error) {
                            console.error('Error querying database:', error);
                            reject(error);
                        } else {
                            const converted_result = result.map(obj => {
                                // Extract necessary values from the object
                                const {id_number, first_name, middle_initial, last_name, balance, roles, number_of_passengers} = obj;
                                // Concatenate values with the desired format
                                return `TAG,${id_number},${first_name} ${middle_initial}. ${last_name},${balance},${roles},${number_of_passengers}`;
                            }).join('\n');
                            resolve(converted_result);
                        }
                    });
                } else {
                    connection.query("UPDATE users_server SET balance = ? WHERE tag_uid = ?", [transaction_balance, tag_id], function (error, result) {
                        if (error) {
                            console.error('Error updating database:', error);
                            reject(error);
                        } else {
                            console.log('Database updated successfully!');
                            resolve(result);
                        }
                    });
                    
                    let user_credit = transaction_balance - current_user[2];
                    let transaction_type1 = "PASSENGER_KIOSK";
                    let currentDate = new Date();
                    let year = currentDate.getFullYear();
                    let month = String(currentDate.getMonth() + 1).padStart(2, '0'); // Months are zero-based
                    let day = String(currentDate.getDate()).padStart(2, '0');
                    let formattedDate = `${year}-${month}-${day}`;
                    console.log(formattedDate);
                    
                    connection.query("INSERT INTO transaction_log (passenger_name, passenger_id_number, passenger_credit, passenger_new_balance, transaction_type, transaction_date) VALUES (?, ?, ?, ?, ?, ?)",
                    [current_user[1], current_user[0], user_credit, transaction_balance, transaction_type1, formattedDate], function (error, result) {
                        if (error) {
                            console.error('Error updating database:', error);
                            reject(error);
                        } else {
                            console.log('Database updated successfully!');
                            resolve(result);
                        }
                    });
                } 
            }
        });
    });
}


function msgToWeb(say){
    io.emit('message to web', say);
}


io.on('connection', (socket) => {
    socket.on('command', (msg) => {
        let msgArray = String(msg).split(',');
        console.log('message: ' + msgArray);
        if(msgArray[0] == "CREDIT AMOUNT"){
            let new_user_balance = parseInt(msgArray[1]);
            console.log('New Balance: ' + new_user_balance);
            databaseConnection(tag_id, new_user_balance);
            msgToEplete("Done"); 
        }
        else if(msgArray[0] == "GO BACK HOME"){
            msgToEplete("Done"); 
        }
    });
});


midApp.listen(3000, () => {
    console.log('listening on *:3000');
});


//+++==========================================================================================================================


function msgToEplete(say){
    lowApp.send(say, appPort, deviceAddress, (err) => {
        console.log('Message {' + say + '} to ' + deviceAddress + ':' + appPort);
    });
}


lowApp.on('listening', async() => {
    const address = lowApp.address();
    console.log(`server listening ${address.address}:${address.port}`);
});


lowApp.on('message', (msg, rinfo) => {
    deviceAddress = rinfo.address;
    appPort = rinfo.port;
    let msgArray = String(msg).split(",");
    if(msgArray[0] == "TAG"){
        tag_id = msgArray[1];
        console.log("TAG ID: " + tag_id);
        async function fetchData(tag_id) {
            try {
              const content = "";
              content = await databaseConnection(tag_id, 0);
              current_user = content.split(",");
              current_user.shift();
              console.log("Current User: " + current_user)
              if (content && current_user[3] == 'RIDER') {
                msgToEplete('Rider');
                setTimeout(() => {
                  console.log("MAIN: " + content);
                  msgToWeb(content);
                }, 2050);
              } else if (content && current_user[3] == 'DRIVER') {
                msgToEplete('Driver');
                setTimeout(() => {
                  console.log("MAIN: " + content);
                  msgToWeb(content);
                }, 2050);
              } else {
                msgToEplete('Invalid');
                msgToWeb('Invalid');
              }
            } catch (error) {
              console.error('Error fetching data:', error);
              msgToEplete('Error');
            }
        }  
        fetchData(tag_id);
    } 
    else if(msgArray[0] == "LOAD"){
        // Forward to Web
        let amount = msgArray[1];
        console.log("Amount: " + amount);
        let content = "LOAD," + amount
        msgToWeb(content);
    }
});

lowApp.bind(5005);
