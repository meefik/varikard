'''
varikard.py
(C) 2011-2014 Anton Skshidlevsky <anton@cde.ifmo.ru>
'''

VERSION = '1.9'

from time import time, sleep
from math import trunc, sqrt
import ConfigParser
import serial
from numpy import linspace, zeros, mean
from numpy.fft import fft
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
import sys
import csv
from os import curdir, sep
from os.path import isfile,basename,dirname,abspath
import json
from optparse import OptionParser

SI = 0
IC = 0
HR = 0
lastRR = 0
lastTime = 0
EKS = []
RR = []

class HttpServerHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        try:
            if self.path == "/varikard":
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                global lastTime,lastRR,SI,IC,RR,HR
                self.wfile.write('{ "UT": %10.3f, "RR": %4d, "sumRR": %6d, "HR": %3d, "SI": %4.2f, "IC": %4.2f }' % (lastTime,lastRR,sum(RR),HR,SI,IC))
                return

            if self.path == "/eks":
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                global EKS
                self.wfile.write(json.dumps(EKS, separators=(',',':')))
                return

            if self.path == "/":
                f = open(curdir + sep + '/index.html')
                self.send_response(200)
                self.send_header('Content-Type','text/html')
                self.end_headers()
                self.wfile.write(f.read())
                f.close()
                return

            if self.path.endswith(".html"):
                f = open(curdir + sep + self.path)
                self.send_response(200)
                self.send_header('Content-Type','text/html')
                self.end_headers()
                self.wfile.write(f.read())
                f.close()
                return

            if self.path.endswith(".js"):
                f = open(curdir + sep + self.path)
                self.send_response(200)
                self.send_header('Content-Type','application/javascript')
                self.end_headers()
                self.wfile.write(f.read())
                f.close()
                return

            if self.path.endswith(".css"):
                f = open(curdir + sep + self.path)
                self.send_response(200)
                self.send_header('Content-Type','text/css')
                self.end_headers()
                self.wfile.write(f.read())
                f.close()
                return

            return
                
        except IOError:
            self.send_error(404,'File Not Found: %s' % self.path)

    def log_message(self, format, *args):
        return


class VarikardAPI(Thread):

    def __init__ (self, params):
        Thread.__init__(self)
        self.loop = True
        self.pkg_size = 6   # bytes
        self.csv_file = params['csv_file']
        self.debug = params['debug']
        self.serial_port = params['serial_port']
        if len(params['kig_file']) > 0:
            self.f_kig = open(params['kig_file'], 'w')
        else:
            self.f_kig = False
        if len(params['eks_file']) > 0:
            self.f_eks = open(params['eks_file'], 'w')
        else:
            self.f_eks = False
        self.hex_format = params['hex_format']
        self.offset = params['offset']
        self.sensitivity = params['sensitivity']
        self.min_int = params['min_int']*1000
        self.max_int = params['max_int']*1000
        self.calc_time = params['calc_time']*1000
        self.signal_timeout = params['signal_timeout']
        self.speedtest_time = params['speedtest_time']
        self.export_eks = params['export_eks']

    def __del__(self):
        if not self.csv_file:
            print "stopping device communications"
            # close device communications
            byteStr = "\x7E\xB3\x31"
            self.ser.write(byteStr)
            self.ser.close()
        if self.f_kig:
            self.f_kig.close()
        if self.f_eks:
            self.f_eks.close()

    def shutdown(self):
        self.loop = False
    
    def run(self):

        global SI,IC,lastRR,lastTime,EKS,point,pkg,signal,RR,timer

        # speed test
        if self.csv_file:
            speed = 1200.0
            print "read data from file: %s" % self.csv_file
        else:
            print "serial port: " + self.serial_port
            # configure the serial connections (the parameters differs on the device you are connecting to)
            self.ser = serial.Serial(
                port=self.serial_port,
                baudrate=115200,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
        
            print "initialize device (Varikard 2.51)"
            # initialize device string
            byteStr = "\x16\x7E\xD0\x4E\x7E\xD0\x00\x4E\x7E\xB3\x31\x7E\xB3\x31\x7E\x01\x7F\x7E\xA1\x1F\x7E\x92\x10"
            # send the characters to the device
            self.ser.write(byteStr)

            read_length = 0
            diffTime = 0
            startTime = time()
            while diffTime < self.speedtest_time:
                buf_size = self.ser.inWaiting()
                self.ser.read(buf_size)
                read_length += buf_size
                diffTime = time() - startTime
            speed = read_length / ( diffTime * self.pkg_size )   # pkg's/sec
            print "speed: %5.2f packages/sec [%5.2f bytes/sec]" % (speed,speed*self.pkg_size)

        point = 1000.0 / speed
        pkg = [0] * self.pkg_size
        signal = []
        timer = 0

        if self.csv_file:
            # read EKS from file
            with open(self.csv_file, 'rb') as csvfile:
                csvreader = csv.reader(csvfile, delimiter=';', quoting=csv.QUOTE_NONE)
                for row in csvreader:
                    if self.loop == False: break
                    # read pkgs
                    for i in range(0,self.pkg_size-1):
                        pkg[i] = int(row[i])

                    pulse = self.CalcRR()

                    sleep(point/1000.0)

            csvfile.close()
        else:
            # read EKS from Varikard
            init_vars = True
            while self.loop:
                if init_vars:
                    init_vars = False
                    SI = 0
                    IC = 0
                    HR = 0
                    lastRR = 0
                    RR = []
                    timer = 0
                    lastTime = time()
                    print ">>> new session"

                if self.ser.inWaiting() < self.pkg_size:
                    continue

                pkg[0] = ord(self.ser.read(1))
                if pkg[0] == 126: # \x7E
                    # read pkgs
                    row = self.ser.read(self.pkg_size-1)
                    for i in range(1,self.pkg_size-1):
                        pkg[i] = ord(row[i])

                    # dump EKS to file
                    if self.f_eks:
                        if self.hex_format:
                            self.f_eks.write(self.ByteToHex(chr(pkg[0]))+';'+self.ByteToHex(chr(pkg[1]))+';'+
                                             self.ByteToHex(chr(pkg[2]))+';'+self.ByteToHex(chr(pkg[3]))+';'+
                                             self.ByteToHex(chr(pkg[4]))+';'+self.ByteToHex(chr(pkg[5]))+'\n')
                        else:
                            self.f_eks.write(str(pkg[0])+';'+str(pkg[1])+';'+str(pkg[2])+';'+
                                             str(pkg[3])+';'+str(pkg[4])+';'+str(pkg[5])+'\n')

                    # timeout
                    if (time() - lastTime) > self.signal_timeout:
                        init_vars = True
                        continue

                    pulse = self.CalcRR()

                    # pulse indicate
                    if pulse:
                        byteStr = "\x7E\xC1\x3F" # on
                        self.ser.write(byteStr)
                    else:
                        byteStr = "\x7E\xC0\x3E" # off
                        self.ser.write(byteStr)

    def CalcRR(self):

        global SI,IC,lastRR,lastTime,EKS,point,pkg,signal,RR,timer,HR

        # skip bad packages
        xtime = pkg[1]*256 + pkg[2]
        if xtime < 32768 or xtime > 65535: 
            return False

        # increment timer
        timer += point

        # signal queue
        signal.append(list(pkg))
        if len(signal) > self.offset:
            signal.pop(0)
        else:
            return False

        # EKS filter
        x = 0.0
        sl = len(signal)/2
        for i in range(0,sl-1):
            x1 = signal[i][4]-signal[i][3]
            x2 = signal[i+sl][4]-signal[i+sl][3]
            x += x1 - x2
        y = x / sl

        # EKS set
        #EKS.append(json.loads('{"x":'+str(time())+',"y":'+str(y)+'}'))
        EKS.append([time()*1000,y])
        if len(EKS) > self.export_eks:
            EKS.pop(0)

        # calc RR intervals
        pulse = False
        if abs(y) >= self.sensitivity and timer >= self.min_int:
            if timer <= self.max_int:
                lastRR = round(timer)
                RR.append(lastRR)
                # calc Heart Rate
                HR = self.CalcHR(lastRR)

                while sum(RR) > self.calc_time:
                    RR.pop(0)

                if sum(RR) >= self.calc_time-self.max_int:
                    # calc SI and IC
                    SI = self.CalcSI(RR)
                    IC = self.CalcIC(RR)

                lastTime = time()
                pulse = True

                # print debug info
                if self.debug:
                    print "time=%10.3f\t sum(RR)=%6d\t RR=%4d\t HR=%3d\t SI=%4.2f\t IC=%4.2f" % (lastTime,sum(RR),lastRR,HR,SI,IC)

                # dump RR interval to file
                if self.f_kig:
                    self.f_kig.write(str(lastTime)+';'+str(lastRR)+'\n')

            timer = 0

        return pulse

    def ByteToHex(self, byteStr):
        """
        Convert a byte string to it's hex string representation e.g. for output.
        """
        # Uses list comprehension which is a fractionally faster implementation than
        # the alternative, more readable, implementation below
        #   
        #    hex = []
        #    for aChar in byteStr:
        #        hex.append( "%02X " % ord( aChar ) )
        #
        #    return ''.join( hex ).strip()        

        return ''.join( [ "%02X " % ord( x ) for x in byteStr ] ).strip()

    def HexToByte(self, hexStr):
        """
        Convert a string hex byte values into a byte string. The Hex Byte values may
        or may not be space separated.
        """
        # The list comprehension implementation is fractionally slower in this case    
        #
        #    hexStr = ''.join( hexStr.split(" ") )
        #    return ''.join( ["%c" % chr( int ( hexStr[i:i+2],16 ) ) \
        #                                   for i in range(0, len( hexStr ), 2) ] )
 
        bytes = []
        hexStr = ''.join( hexStr.split(" ") )
        for i in range(0, len(hexStr), 2):
            bytes.append( chr( int (hexStr[i:i+2], 16 ) ) )

        return ''.join( bytes )

    def CalcHR(self, x):
        return round(1000.0/x*60.0)

    def CalcSI(self, x):
        dNN = 50  # milliseconds
        n = len(x)
        Mn = min(x)
        Mx = max(x)
        MxDMn = Mx - Mn
        k =  trunc( MxDMn / dNN ) + 1
        #k = trunc(1.72 * n**(1.0/3.0))
        hist = zeros(k, float)
        for i in range(0,n-1):
            for j in range(0,k-2):
                if (x[i] >= Mn + dNN*j) and (x[i] < Mn + dNN*(j+1)):
                    hist[j] += 1.0
        h_max = max(hist)
        Mo = sum(x)/n
        for i in range(0,k-1):
            if hist[i] == h_max:
                Mo = Mn + dNN*i
            hist[i] = hist[i] / n
        Amo = max(hist) * 100.0
        SI = Amo / ( 2 * Mo / 1000 * MxDMn / 1000) 
        return SI

    # Find 2^n that is equal to or greater than 
    def nextpow2(self, i):
        n = 2
        while n < i:
            n = n * 2
        return n

    def CalcIC(self, x):
        Fs = 1.0                # Frequency (Hz)
        L = len(x)
        NFFT = self.nextpow2(L)
        Y = fft(x, NFFT)
        f = Fs / 2 * linspace(0, 1, NFFT / 2 + 1)
        power = Y*Y.conjugate()
        ULF = 0
        VLF = 0
        LF = 0
        HF = 0
        for i in range(1,len(f)):
            if (f[i] > 0.002) and (f[i] <= 0.015):
                ULF = ULF + 2*power[i].real
            elif (f[i] > 0.015) and (f[i] <= 0.04):
                VLF = VLF + 2*power[i].real
            elif (f[i] > 0.04) and (f[i] <= 0.15):
                LF = LF + 2*power[i].real
            elif (f[i] > 0.15) and (f[i] <= 0.4):
                HF = HF + 2*power[i].real
        IC = (LF + VLF) / HF
        return IC

def main(argv):
    # parsing input arguments
    parser = OptionParser()
    parser.add_option("-f", "--csv-file", dest="csv_file",
                  help="read electrocardiosignal from CSV file", metavar="FILE")
    parser.add_option("-d", "--debug",
                  action="store_true", dest="debug", default=False,
                  help="print debug messages to stdout")
    parser.add_option("-v", "--version",
                  action="store_true", dest="version", default=False,
                  help="print version information")
    (options, args) = parser.parse_args()

    if options.version:
        print "%s version %s" % (basename(__file__), VERSION)
        sys.exit(0)

    # read config file
    config = ConfigParser.RawConfigParser()
    config.read(dirname(abspath(__file__))+sep+'varikard.conf')

    params = {
    'host': config.get('general', 'host'),
    'port': int(config.get('general', 'port')),
    'debug': options.debug,
    'csv_file': (options.csv_file,False)[options.csv_file == None],
    'serial_port': config.get('general', 'serial_port'),
    'kig_file': config.get('general', 'kig_file'),
    'eks_file': config.get('general', 'eks_file'),
    'hex_format': config.get('general', 'hex_format').lower() in ("yes", "true", "1"),
    'export_eks': int(config.get('general', 'export_eks')),
    'offset': int(config.get('filter', 'offset')),
    'sensitivity': int(config.get('filter', 'sensitivity')),
    'min_int': float(config.get('filter', 'min_int')),
    'max_int': float(config.get('filter', 'max_int')),
    'calc_time': int(config.get('filter', 'calc_time')),
    'signal_timeout': int(config.get('filter', 'signal_timeout')),
    'speedtest_time': int(config.get('filter', 'speedtest_time'))
    }
    
    try:
        dev = VarikardAPI(params)
        dev.start()
        server = HTTPServer((params['host'], params['port']), HttpServerHandler)
        print 'starting httpserver'
        server.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        dev.shutdown()
        print 'shutting down httpserver'
        server.socket.close()

if __name__ == '__main__':
    main(sys.argv[1:])
