#! /bin/sh
"true" '''\'
if command -v python2 > /dev/null; then
  exec python2 "$0" "$@"
else
  exec python "$0" "$@"
fi
exit $?
'''
#    LibVirt Wake On Lan
#    Copyright (C) 2012 Simon Cadman
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
import pcap
import sys
import socket
import struct
import string
import libvirt
from xml.dom import minidom


class LibVirtWakeOnLan:
    
    @staticmethod
    def StartServerByMACAddress(mac):
        conn = libvirt.open(None)
        if conn is None:
            print 'Failed to open connection to the hypervisor'
            sys.exit(1)

        domains = conn.listDefinedDomains()
        for domainName in domains:
            domain = conn.lookupByName(domainName)
            params = []
            # TODO - replace with api calls to fetch network interfaces
            xml = minidom.parseString(domain.XMLDesc(0))
            devices = xml.documentElement.getElementsByTagName("devices")
            for device in devices:
                for interface in device.getElementsByTagName("interface"):
                    macadd = interface.getElementsByTagName("mac")
                    foundmac = macadd[0].getAttribute("address")
                    if foundmac == mac:
                        print "Waking up", domainName
                        domain.create()
                        return

    @staticmethod
    def GetMACAddress(s):
        if len(s) == 110:
            bytes = map(lambda x: '%.2x' % x, map(ord, s))
            counted = 0
            macpart = 0
            maccounted = 0
            macaddress = None
            newmac = ""

            for byte in bytes:
                if counted < 6:
                    # find 6 repetitions of 255
                    if byte == "ff":
                        counted += 1
                else:
                    # find 16 repititions of 48 bit mac
                    macpart += 1
                    if newmac != "":
                        newmac += ":"

                    newmac += byte

                    if macpart is 6 and macaddress is None:
                        macaddress = newmac

                    if macpart is 6:
                        if macaddress != newmac:
                            return None
                        newmac = ""
                        macpart = 0
                        maccounted += 1

            if counted == 6 and maccounted == 16:
                return macaddress

    @staticmethod
    def DecodeIPPacket(s):
        d = {}
        d['version'] = (ord(s[0]) & 0xf0) >> 4
        d['header_len'] = ord(s[0]) & 0x0f
        d['tos'] = ord(s[1])
        d['total_len'] = socket.ntohs(struct.unpack('H', s[2:4])[0])
        d['id'] = socket.ntohs(struct.unpack('H', s[4:6])[0])
        d['flags'] = (ord(s[6]) & 0xe0) >> 5
        d['fragment_offset'] = socket.ntohs(struct.unpack('H', s[6:8])[0] & 0x1f)
        d['ttl'] = ord(s[8])
        d['protocol'] = ord(s[9])
        d['checksum'] = socket.ntohs(struct.unpack('H', s[10:12])[0])
        d['source_address'] = pcap.ntoa(struct.unpack('i', s[12:16])[0])
        d['destination_address'] = pcap.ntoa(struct.unpack('i', s[16:20])[0])
        if d['header_len'] > 5:
            d['options'] = s[20:4 * (d['header_len'] - 5)]
        else:
            d['options'] = None
        d['data'] = s[4 * d['header_len']:]
        return d

    @staticmethod
    def InspectIPPacket(pktlen, data, timestamp):
        if not data:
            return
        decoded = LibVirtWakeOnLan.DecodeIPPacket(data[14:])
        macaddress = LibVirtWakeOnLan.GetMACAddress(decoded['data'])
        if not macaddress:
            return
        LibVirtWakeOnLan.StartServerByMACAddress(macaddress)

if __name__ == '__main__':
    from lvwolutils import Utils

    # line below is replaced on commit
    LVWOLVersion = "20140807 113906"
    Utils.ShowVersion(LVWOLVersion)

    if len(sys.argv) < 2:
        print('usage: libvirtwol <interface>')
        sys.exit(0)

    interface = sys.argv[1]
    p = pcap.pcapObject()
    net, mask = pcap.lookupnet(interface)
    p.open_live(interface, 1600, 0, 100)
    p.setfilter('udp and port 7 or port 9', 0, 0)

    try:
        while 1:
            p.dispatch(1, LibVirtWakeOnLan.InspectIPPacket)
    except KeyboardInterrupt:
        pass
