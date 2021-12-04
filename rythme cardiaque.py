from spidev import SpiDev

class MCP3008:
    def __init__(self, bus = 0, device = 0):
        self.bus, self.device = bus, device
        self.spi = SpiDev()
        self.open()
        self.spi.max_speed_hz = 1000000 # 1MHz

    def open(self):
        self.spi.open(self.bus, self.device)
        self.spi.max_speed_hz = 1000000 # 1MHz
    
    def read(self, channel = 0):
        cmd1 = 4 | 2 | (( channel & 4) >> 2)
        cmd2 = (channel & 3) << 6

        adc = self.spi.xfer2([cmd1, cmd2, 0])
        data = ((adc[1] & 15) << 8) + adc[2]
        return data
            
    def close(self):
        self.spi.close()
        
import time
import threading
from MCP3008 import MCP3008

class Pulsesensor:
    def __init__(self, channel = 0, bus = 0, device = 0):
        self.channel = channel
        self.BPM = 0
        self.adc = MCP3008(bus, device)

    def getBPMLoop(self):
        # init variables
        rate = [0] * 10         # tableau pour contenir les 10 dernières valeurs IBI
        sampleCounter = 0       #utilisé pour déterminer la synchronisation des impulsions
        lastBeatTime = 0        # utilisé pour trouver IBI
        P = 512                 # utilisé pour trouver le pic dans l'onde de pouls
        T = 512                 #utilisé pour trouver le creux dans l'onde de pouls
        thresh = 525            #utilisé pour trouver un moment de battement cardiaque instantané
        amp = 100               #utilisé pour maintenir l'amplitude de la forme d'onde d'impulsion
        firstBeat = True        #utilisé pour le tableau de taux afin que nous démarrons avec un BPM raisonnable
        secondBeat = False      #utilisé pour le tableau de taux afin que nous démarrons avec un BPM raisonnable

        IBI = 600               #int qui contient l'intervalle de temps entre les battements !
        Pulse = False           #« True » lorsque le rythme cardiaque en direct de l'utilisateur est détecté. "False" quand ce n'est pas un "live beat". 
        lastTime = int(time.time()*1000)
        
        while not self.thread.stopped:
            Signal = self.adc.read(self.channel)
            currentTime = int(time.time()*1000)
            
            sampleCounter += currentTime - lastTime
            lastTime = currentTime
            
            N = sampleCounter - lastBeatTime

            # find the peak and trough of the pulse wave
            if Signal < thresh and N > (IBI/5.0)*3:     #évitez le bruit dichrotique en attendant les 3/5 du dernier IBI
                if Signal < T:                          #T est le creux
                    T = Signal                          #suivre le point le plus bas de l'onde de pouls 

            if Signal > thresh and Signal > P:
                P = Signal

            #le signal augmente de valeur à chaque fois qu'il y a une impulsion
            if N > 250:                                 #éviter le bruit à haute fréquence
                if Signal > thresh and Pulse == False and N > (IBI/5.0)*3:       
                    Pulse = True                        #définir le drapeau Pulse lorsque nous pensons qu'il y a une impulsion
                    IBI = sampleCounter - lastBeatTime  #mesurer le temps entre les battements en mS
                    lastBeatTime = sampleCounter        #garder une trace du temps pour la prochaine impulsion

                    if secondBeat:                      #si c'est le deuxième temps, si secondBeat == TRUE
                        secondBeat = False;             #effacer le drapeau secondBeat
                        for i in range(len(rate)):      #semer le total cumulé pour obtenir un BPM réaliste au démarrage
                          rate[i] = IBI

                    if firstBeat:                       #si c'est la première fois qu'on trouve un beat, si firstBeat == TRUE
                        firstBeat = False;              #effacer le drapeau firstBeat
                        secondBeat = True;              #définir le deuxième indicateur de temps
                        continue

                    #garder un total cumulé des 10 dernières valeurs IBI  
                    rate[:-1] = rate[1:]                #décaler les données dans le tableau de taux
                    rate[-1] = IBI                      #ajouter le dernier IBI au tableau des taux
                    runningTotal = sum(rate)            #ajouter les valeurs IBI les plus anciennes

                    runningTotal /= len(rate)           #faire la moyenne des valeurs IBI
                    self.BPM = 60000/runningTotal       #combien de battements peuvent tenir dans une minute ? c'est le BPM !

            if Signal < thresh and Pulse == True:       #quand les valeurs baissent, le rythme est terminé
                Pulse = False                           #réinitialiser le drapeau Pulse afin que nous puissions le refaire
                amp = P - T                             #obtenir l'amplitude de l'onde de pouls
                thresh = amp/2 + T                      #régler le seuil à 50% de l'amplitude
                P = thresh                              #réinitialisez-les pour la prochaine fois
                T = thresh

            if N > 2500:                                #si 2,5 secondes s'écoulent sans un battement
                thresh = 512                            #définir le seuil par défaut
                P = 512                                 #définir P par défaut
                T = 512                                 # définir T par défaut
                lastBeatTime = sampleCounter            # mettre à jour le lastBeatTime        
                firstBeat = True                        # réglez-les pour éviter le bruit
                secondBeat = False                      #quand on retrouve le rythme cardiaque
                self.BPM = 0

            time.sleep(0.005)
            
# Lancer la routine getBPMLoop qui enregistre le BPM dans sa variable
    def startAsyncBPM(self):
        self.thread = threading.Thread(target=self.getBPMLoop)
        self.thread.stopped = False
        self.thread.start()
        return
        
    #Arrêtez la routine
    def stopAsyncBPM(self):
        self.thread.stopped = True
        self.BPM = 0
        return
   
from pulsesensor import Pulsesensor
import time

p = Pulsesensor()
p.startAsyncBPM()

try:
    while True:
        bpm = p.BPM
        if bpm > 0:
            print("BPM: %d" % bpm)
        else:
            print("No Heartbeat found")
        time.sleep(1)
except:
    p.stopAsyncBPM()
