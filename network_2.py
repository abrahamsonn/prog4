import Queue as queue
import sys
import threading


## wrapper class for a queue of packets
class Interface:
    #type = "interface"

    ## @param maxsize - the maximum size of the queue storing packets
    def __init__(self, maxsize=0):
        self.in_queue = queue.Queue(maxsize)
        self.out_queue = queue.Queue(maxsize)
    
    ##get packet from the queue interface
    # @param in_or_out - use 'in' or 'out' interface
    def get(self, in_or_out):
        try:
            if in_or_out == 'in':
                pkt_S = self.in_queue.get(False)
                # if pkt_S is not None:
                #     print('getting packet from the IN queue')
                return pkt_S
            else:
                pkt_S = self.out_queue.get(False)
                # if pkt_S is not None:
                #     print('getting packet from the OUT queue')
                return pkt_S
        except queue.Empty:
            return None
        
    ##put the packet into the interface queue
    # @param pkt - Packet to be inserted into the queue
    # @param in_or_out - use 'in' or 'out' interface
    # @param block - if True, block until room in queue, if False may throw queue.Full exception
    def put(self, pkt, in_or_out, block=False):
        if in_or_out == 'out':
            # print('putting packet in the OUT queue')
            self.out_queue.put(pkt, block)
        else:
            # print('putting packet in the IN queue')
            self.in_queue.put(pkt, block)
            
        
## Implements a network layer packet.
class NetworkPacket:
    #type = "networkpacket"
    ## packet encoding lengths 
    dst_S_length = 5
    prot_S_length = 1
    
    ##@param dst: address of the destination host
    # @param data_S: packet payload
    # @param prot_S: upper layer protocol for the packet (data, or control)
    def __init__(self, dst, prot_S, data_S):
        self.dst = dst
        self.data_S = data_S
        self.prot_S = prot_S
        
    ## called when printing the object
    def __str__(self):
        return self.to_byte_S()
        
    ## convert packet to a byte string for transmission over links
    def to_byte_S(self):
        byte_S = str(self.dst).zfill(self.dst_S_length)
        if self.prot_S == 'data':
            byte_S += '1'
        elif self.prot_S == 'control':
            byte_S += '2'
        else:
            raise('%s: unknown prot_S option: %s' %(self, self.prot_S))
        byte_S += str(self.data_S) # fuck this language
        return byte_S
    
    ## extract a packet object from a byte string
    # @param byte_S: byte string representation of the packet
    @classmethod
    def from_byte_S(self, byte_S):
        dst = byte_S[0 : NetworkPacket.dst_S_length].strip('0')
        prot_S = byte_S[NetworkPacket.dst_S_length : NetworkPacket.dst_S_length + NetworkPacket.prot_S_length]
        if prot_S == '1':
            prot_S = 'data'
        elif prot_S == '2':
            prot_S = 'control'
        else:
            raise('%s: unknown prot_S field: %s' %(self, prot_S))
        data_S = byte_S[NetworkPacket.dst_S_length + NetworkPacket.prot_S_length : ]        
        return self(dst, prot_S, data_S)
    

    

## Implements a network host for receiving and transmitting data
class Host:
    #type = "host"
    
    ##@param addr: address of this node represented as an integer
    def __init__(self, addr):
        self.addr = addr
        self.intf_L = [Interface()]
        self.stop = False #for thread termination
    
    ## called when printing the object
    def __str__(self):
        return self.addr
       
    ## create a packet and enqueue for transmission
    # @param dst: destination address for the packet
    # @param data_S: data being transmitted to the network layer
    def udt_send(self, dst, data_S):
        p = NetworkPacket(dst, 'data', data_S)
        print('%s: sending packet "%s"' % (self, p))
        self.intf_L[0].put(p.to_byte_S(), 'out') #send packets always enqueued successfully
        
    ## receive packet from the network layer
    def udt_receive(self):
        pkt_S = self.intf_L[0].get('in')
        if pkt_S is not None:
            print('%s: received packet "%s"' % (self, pkt_S))
       
    ## thread target for the host to keep receiving data
    def run(self):
        print (threading.currentThread().getName() + ': Starting')
        while True:
            #receive data arriving to the in interface
            self.udt_receive()
            #terminate
            if(self.stop):
                print (threading.currentThread().getName() + ': Ending')
                return
        


## Implements a multi-interface router
class Router:

    #type = "router"

    ##@param name: friendly router name for debugging
    # @param cost_D: cost table to neighbors {neighbor: {interface: cost}}
    # @param max_queue_size: max queue length (passed to Interface)
    def __init__(self, name, cost_D, max_queue_size):
        self.stop = False #for thread termination
        self.name = name
        #create a list of interfaces
        self.intf_L = [Interface(max_queue_size) for _ in range(len(cost_D))]
        #save neighbors and interfeces on which we connect to them
        self.cost_D = cost_D    # {neighbor: {interface: cost}}
        #TODO: set up the routing table for connected hosts
        self.rt_tbl_D = {"H1": {"RA": 99, "RB": 99},
            "H2": {"RA": 99, "RB": 99},
            "RA": {"RA": 99, "RB": 99},
            "RB": {"RA": 99, "RB": 99}}            # {destination: {router: cost}}
        print('%s: Initialized routing table' % self)
        self.print_routes()
        self.rt_tbl_D[str(self)][str(self)] = 0
        for neighbor in self.cost_D:
            for interface in self.cost_D[neighbor]:
                self.rt_tbl_D[neighbor][str(self)] = self.cost_D[neighbor][interface]
        for neighbor in self.cost_D:
            for interface in self.cost_D[neighbor]:
                self.send_routes(interface)

    ## called when printing the object
    def __str__(self):
        return self.name


    ## look through the content of incoming interfaces and 
    # process data and control packets
    def process_queues(self):
        for i in range(len(self.intf_L)):
            pkt_S = None
            #get packet from interface i
            pkt_S = self.intf_L[i].get('in')
            #if packet exists make a forwarding decision
            if pkt_S is not None:
                p = NetworkPacket.from_byte_S(pkt_S) #parse a packet out
                if p.prot_S == 'data':
                    self.forward_packet(p,i)
                elif p.prot_S == 'control':
                    self.update_routes(p, i)
                else:
                    raise Exception('%s: Unknown packet type in packet %s' % (self, p))
            

    ## forward the packet according to the routing table
    #  @param p Packet to forward
    #  @param i Incoming interface number for packet p
    def forward_packet(self, p, i):
        # TODO: Here you will need to implement a lookup into the 
        # forwarding table to find the appropriate outgoing interface
        # for now we assume the outgoing interface is 1
        try:
            # get packet info
            dest_addr = p.dst
            interface_out = self.rt_tbl_D[dest_addr]
            print("\tDEST ADDR = %s\n\tPOSSIBLE COSTS = %s" % (str(dest_addr), str(interface_out)))
            # get lowest cost
            min_value = 99
            for x in interface_out:
                if min_value > interface_out[x]:
                    min_value = interface_out[x]
                    send_to_router = x

            # get interface #
            for key in self.cost_D:
                if self.cost_D[key] == min_value:
                    out_interface = key
                    print("out_interface = %s\n" % str(out_interface))

            print("send_to_router = %s" % str(send_to_router))

            self.intf_L[1].put(p.to_byte_S(), 'out', True)
            print('%s: forwarding packet "%s" from interface %d to %d' % \
                (self, p, i, 1))
        except queue.Full:
            print('%s: packet "%s" lost on interface %d' % (self, p, i))
            pass


    ## send out route update
    # @param i Interface number on which to send out a routing update
    def send_routes(self, i):
        # TODO: Send out a routing table update
        #create a routing table update packet
        string_to_send = ''
        for destinationColumn in self.rt_tbl_D:
            for routerRow in self.rt_tbl_D[destinationColumn]:
                string_to_send += ''.join([destinationColumn, routerRow, str(self.rt_tbl_D[destinationColumn][routerRow]).zfill(2)])
        update_packet = NetworkPacket(0, 'control', string_to_send)
        try:
            print('%s: sending routing update from interface %d' % (self, i))
            self.print_routes()
            self.intf_L[i].put(update_packet.to_byte_S(), 'out', True) # why encode the table when to_byte_S does it already
        except queue.Full:
            print('%s: packet "%s" lost on interface %d' % (self, p, i))
            pass

    ## forward the packet according to the routing table
    #  @param p Packet containing routing information
    def update_routes(self, updated_packet, i):
        #TODO: add logic to update the routing tables and
        # possibly send out routing updates
        print('%s: Received routing update %s from interface %d' % (self, updated_packet.data_S, i))
        updateString = updated_packet.data_S
        indexOfString = 0
        didUpdate = False
        temp = ''
        looping = True
        while(looping):
            currentDestination = updateString[indexOfString:indexOfString+2]
            indexOfString += 2
            currentRouter = updateString[indexOfString:indexOfString+2]
            indexOfString += 2
            currentCost = int(updateString[indexOfString:indexOfString+2])
            indexOfString += 2
            existingValue = self.rt_tbl_D[currentDestination][currentRouter]
            if currentCost < existingValue:
                self.rt_tbl_D[currentDestination][currentRouter] = currentCost
                didUpdate = True
            if indexOfString >= len(updateString):
                looping = False
        for neighbor in self.cost_D:
            if neighbor[0] == 'R':
                for destinationColumn in self.rt_tbl_D:
                    currentCost = self.rt_tbl_D[destinationColumn][str(self)]
                    potentialCost = self.rt_tbl_D[destinationColumn][neighbor] + self.rt_tbl_D[neighbor][str(self)]
                    if potentialCost < currentCost:
                        self.rt_tbl_D[destinationColumn][str(self)] = potentialCost
                        didUpdate = True
        if didUpdate:
            for neighbor in self.cost_D:
                if neighbor[0] == 'R':
                    for interface in self.cost_D[neighbor]:
                        self.send_routes(interface)
        
    ## P routing table
    def print_routes(self):
         print "\n________________________\n" + \
            "|" + str(self) + " | H1 | H2 | RA | RB |\n" + \
            "|-----------------------|\n" + \
            "|RA | "+str(self.rt_tbl_D["H1"]["RA"]).zfill(2)+" | "+str(self.rt_tbl_D["H2"]["RA"]).zfill(2)+" | "+str(self.rt_tbl_D["RA"]["RA"]).zfill(2)+" | "+str(self.rt_tbl_D["RB"]["RA"]).zfill(2)+" |\n" + \
            "|-----------------------|\n" + \
            "|RB | "+str(self.rt_tbl_D["H1"]["RB"]).zfill(2)+" | "+str(self.rt_tbl_D["H2"]["RB"]).zfill(2)+" | "+str(self.rt_tbl_D["RA"]["RB"]).zfill(2)+" | "+str(self.rt_tbl_D["RB"]["RB"]).zfill(2)+" |\n" + \
            "------------------------\n"

    ## thread target for the host to keep forwarding data
    def run(self):
        print (threading.currentThread().getName() + ': Starting')
        while True:
            self.process_queues()
            if self.stop:
                print (threading.currentThread().getName() + ': Ending')
                return 
