print("Starting imports...")
import matplotlib
matplotlib.use('Agg')
from alhazen.quadraticEstimator import Estimator
import orphics.maps as fmaps 
from orphics.cosmology import loadTheorySpectraFromCAMB
import numpy as np
#from astLib import astWCS, astCoords
import flipper.liteMap as lm
from orphics.io import Plotter
from orphics.stats import bin_in_annuli
import sys

from scipy.interpolate import interp1d
from scipy.fftpack import fft2,ifft2,fftshift,ifftshift,fftfreq
#from scipy.fftpack import fftshift,ifftshift,fftfreq
# from pyfftw.interfaces.scipy_fftpack import fft2
# from pyfftw.interfaces.scipy_fftpack import ifft2

# import pyfftw
# pyfftw.interfaces.cache.enable()

import flipper.fftTools as ft
import orphics.tools.stats as stats


from orphics.stats import get_stats

from mpi4py import MPI

print("Done with imports...")

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
numcores = comm.Get_size()    


loadFile = None #"/astro/astronfs01/workarea/msyriac/act/normDec14_0_trimmed.pkl" #None
saveFile = None #"/astro/astronfs01/workarea/msyriac/act/normDec14_0_trimmed_ellmin500.pkl"
trimmed = False
cutout = False

noiseT = 1.
noiseP = np.sqrt(2.)*noiseT


suffix = ""
if trimmed: suffix = "_down"

periodic = "periodic_"
cutoutStr = ""
if cutout: 
    periodic = ""
    cutoutStr = "_cutout"

#polCombList = ['TT','EE','EB','TB','TE','ET']
polCombList = ['TT','EB']
colorList = ['red','blue','green','orange','purple','brown']
tonly = False
if polCombList==['TT']: tonly=True

simRoot = "/gpfs01/astro/workarea/msyriac/data/sims/alex/"

lensedTPath = lambda x: simRoot + "s14/lensedCMBMaps_" + str(x).zfill(5) + "/order5_"+periodic+"lensedCMB_T_beam"+cutoutStr+"_0"+suffix+".fits"
lensedQPath = lambda x: simRoot + "s14/lensedCMBMaps_" + str(x).zfill(5) + "/order5_"+periodic+"lensedCMB_Q_beam"+cutoutStr+"_0"+suffix+".fits"
lensedUPath = lambda x: simRoot + "s14/lensedCMBMaps_" + str(x).zfill(5) + "/order5_"+periodic+"lensedCMB_U_beam"+cutoutStr+"_0"+suffix+".fits"
kappaPath = lambda x: simRoot + "s14/phiMaps_" + str(x).zfill(5) + "/kappaMap"+cutoutStr+"_0"+suffix+".fits"
beamPath = simRoot + "beam_0.txt"

l,beamells = np.loadtxt(beamPath,unpack=True,usecols=[0,1])

cmbellmin = 100
cmbellmax = 3000
kellmin = 100
kellmax = 3000

#cambRoot = "/astro/u/msyriac/repos/cmb-lensing-projections/data/TheorySpectra/ell28k_highacc"
cambRoot = "/gpfs01/astro/workarea/msyriac/data/sims/alex/non-linear"

TCMB = 2.7255e6
#theory = loadTheorySpectraFromCAMB(cambRoot,unlensedEqualsLensed=False,useTotal=False,TCMB = TCMB,lpad=4000)
# !!!!!!!!!!!!! N2 bias
theory = loadTheorySpectraFromCAMB(cambRoot,unlensedEqualsLensed=True,useTotal=False,TCMB = TCMB,lpad=(cmbellmax + 500))

ellkk = np.arange(2,9000,1)
Clkk = theory.gCl("kk",ellkk)    

N = int(sys.argv[1])

assert N%numcores==0

num_each = (N / numcores)
startIndex = rank*num_each
endIndex = startIndex + num_each
myIs = list(range(N))[startIndex:endIndex]


listCrossPower = {}
listReconPower = {}



for polComb in polCombList:
    listCrossPower[polComb] = []
    listReconPower[polComb] = []




bin_edges = np.arange(kellmin,kellmax,80)

whiteNoiseT = (np.pi / (180. * 60))**2.  * noiseT**2. #/ TCMB**2.  
whiteNoiseP = (np.pi / (180. * 60))**2.  * noiseP**2. #/ TCMB**2.  


for k,i in enumerate(myIs):
    print(i)

    lensedTLm = lm.liteMapFromFits(lensedTPath(i))
    lensedQLm = lm.liteMapFromFits(lensedQPath(i))
    lensedULm = lm.liteMapFromFits(lensedUPath(i))
    kappaLm = lm.liteMapFromFits(kappaPath(i))

    

    if k==0:
        lxMap,lyMap,modLMap,thetaMap,lx,ly = fmaps.getFTAttributesFromLiteMap(lensedTLm)
        beamTemplate = fmaps.makeTemplate(l,beamells,modLMap)
        fMaskCMB = fmaps.fourierMask(lx,ly,modLMap,lmin=cmbellmin,lmax=cmbellmax)
        fMask = fmaps.fourierMask(lx,ly,modLMap,lmin=kellmin,lmax=kellmax)

        ellNoise = np.arange(0,modLMap.max())
        Ntt = ellNoise*0.+whiteNoiseT
        Npp = ellNoise*0.+whiteNoiseP
        Ntt[0] = 0.
        Npp[0] = 0.
        gGenT = fmaps.GRFGen(lensedTLm.copy(),ellNoise,Ntt,bufferFactor=1)
        gGenP1 = fmaps.GRFGen(lensedTLm.copy(),ellNoise,Npp,bufferFactor=1)
        gGenP2 = fmaps.GRFGen(lensedTLm.copy(),ellNoise,Npp,bufferFactor=1)


    if noiseT>1.e-3: lensedTLm.data = lensedTLm.data + gGenT.getMap(stepFilterEll=None)
    if noiseP>1.e-3: lensedQLm.data = lensedQLm.data + gGenP1.getMap(stepFilterEll=None)
    if noiseP>1.e-3: lensedULm.data = lensedULm.data + gGenP2.getMap(stepFilterEll=None)

    # pl = Plotter()
    # pl.plot2d(lensedTLm.data)
    # pl.done("map.png")
    # sys.exit()
        
    fot,foe,fob = fmaps.TQUtoFourierTEB(lensedTLm.data.copy().astype(float)/TCMB,lensedQLm.data.copy().astype(float)/TCMB,lensedULm.data.copy().astype(float)/TCMB,modLMap,thetaMap)



        

    fot[:,:] = (fot[:,:] / beamTemplate[:,:])
    foe[:,:] = (foe[:,:] / beamTemplate[:,:])
    fob[:,:] = (fob[:,:] / beamTemplate[:,:])
    filt_noiseT = fot.copy()*0.+gGenT.power/ beamTemplate[:,:]**2./TCMB**2.
    filt_noiseE = fot.copy()*0.+gGenP1.power/ beamTemplate[:,:]**2./TCMB**2.
    filt_noiseB = fot.copy()*0.+gGenP2.power/ beamTemplate[:,:]**2./TCMB**2.
    

    if k==0:


        qest = Estimator(lensedTLm,
                         theory,
                         theorySpectraForNorm=None,
                         noiseX2dTEB=[filt_noiseT,filt_noiseE,filt_noiseB],
                         noiseY2dTEB=[filt_noiseT,filt_noiseE,filt_noiseB],
                         fmaskX2dTEB=[fMaskCMB]*3,
                         fmaskY2dTEB=[fMaskCMB]*3,
                         fmaskKappa=fMask,
                         doCurl=False,
                         TOnly=tonly,
                         halo=True,
                         gradCut=cmbellmax,verbose=True,
                         loadPickledNormAndFilters=loadFile,
                         savePickledNormAndFilters=saveFile)




    print(("Reconstructing" , i , " ..."))
    qest.updateTEB_X(fot,foe,fob,alreadyFTed=True)
    qest.updateTEB_Y(alreadyFTed=True)

    for j, polComb in enumerate(polCombList):

        kappa = qest.getKappa(polComb)

        # pl = Plotter()
        # pl.plot2d(fftshift(qest.AL[polComb]))
        # pl.done("al.png")
        # sys.exit()

        reconLm = lensedTLm.copy()
        reconLm.data[:,:] = kappa[:,:].real

        print("crossing with input")


        p2d = ft.powerFromLiteMap(kappaLm,reconLm,applySlepianTaper=False)
        centers, means = stats.bin_in_annuli(p2d.powerMap, p2d.modLMap, bin_edges)
        listCrossPower[polComb].append( means )



        p2d = ft.powerFromLiteMap(reconLm,applySlepianTaper=False)
        centers, means = stats.bin_in_annuli(p2d.powerMap, p2d.modLMap, bin_edges)
        listReconPower[polComb].append( means )

    p2d = ft.powerFromLiteMap(kappaLm,applySlepianTaper=False)
    centers, means = stats.bin_in_annuli(p2d.powerMap, p2d.modLMap, bin_edges)

    if k==0: totInputPower = (means.copy()*0.).astype(dtype=np.float64)

    totInputPower = totInputPower + means




if rank!=0:
    for i,polComb in enumerate(polCombList):
        data = np.array(listCrossPower[polComb],dtype=np.float64)
        comm.Send(data.copy(), dest=0, tag=i)
        data = np.array(listReconPower[polComb],dtype=np.float64)
        comm.Send(data.copy(), dest=0, tag=i+80)
        
    comm.Send(totInputPower.copy(), dest=0, tag=800)
        
else:

    totAllInputPower = totInputPower
    rcvTotInputPower = totAllInputPower.copy()*0.


    listAllCrossPower = {}
    listAllReconPower = {}

    for polComb in polCombList:
        listAllCrossPower[polComb] = np.array(listCrossPower[polComb],dtype=np.float64)
        listAllReconPower[polComb] = np.array(listReconPower[polComb],dtype=np.float64)
    

    rcvInputPowerMat = listAllReconPower['TT'].copy()*0.



    for job in range(1,numcores):
        comm.Recv(rcvTotInputPower, source=job, tag=800)
        totAllInputPower = totAllInputPower + rcvTotInputPower

        for i,polComb in enumerate(polCombList):
            print(("Waiting for ", job ," ", polComb," cross"))
            comm.Recv(rcvInputPowerMat, source=job, tag=i)
            listAllCrossPower[polComb] = np.vstack((listAllCrossPower[polComb],rcvInputPowerMat))
            print(("Waiting for ", job ," ", polComb," auto"))
            comm.Recv(rcvInputPowerMat, source=job, tag=i+80)
            listAllReconPower[polComb] = np.vstack((listAllReconPower[polComb],rcvInputPowerMat))
        

    statsCross = {}
    statsRecon = {}

    pl = Plotter(scaleY='log')
    pl.add(ellkk,Clkk,color='black',lw=2)
    

    for polComb,col in zip(polCombList,colorList):
        statsCross[polComb] = get_stats(listAllCrossPower[polComb])
        pl.addErr(centers,statsCross[polComb]['mean'],yerr=statsCross[polComb]['errmean'],ls="none",marker="o",markersize=8,label="recon x input "+polComb,color=col,mew=2,elinewidth=2)

        statsRecon[polComb] = get_stats(listAllReconPower[polComb])
        fp = interp1d(centers,statsRecon[polComb]['mean'],fill_value='extrapolate')
        pl.add(ellkk,(fp(ellkk))-Clkk,color=col,lw=2)

        Nlkk2d = qest.N.Nlkk[polComb]
        ncents, npow = stats.bin_in_annuli(Nlkk2d, p2d.modLMap, bin_edges)
        pl.add(ncents,npow,color=col,lw=2,ls="--")

        


    avgInputPower  = totAllInputPower/N
    pl.add(centers,avgInputPower,color='cyan',lw=3) # ,label = "input x input"


    pl.legendOn(labsize=10,loc='lower left')
    pl._ax.set_xlim(kellmin,kellmax)
    pl.done("tests/output/power.png")


    # cross compare to power of input (percent)
    pl = Plotter()

    for polComb,col in zip(polCombList,colorList):
        cross = statsCross[polComb]['mean']
        
        
        pl.add(centers,(cross-avgInputPower)*100./avgInputPower,label=polComb,color=col,lw=2)


    pl.legendOn(labsize=10,loc='upper right')
    pl._ax.set_xlim(kellmin,kellmax)
    pl._ax.axhline(y=0.,ls="--",color='black',alpha=0.5)
    pl._ax.set_ylim(-10.,10.)
    pl.done("tests/output/percent.png")

    # cross compare to power of input (bias)
    pl = Plotter()

    for polComb,col in zip(polCombList,colorList):
        cross = statsCross[polComb]['mean']
        crossErr = statsCross[polComb]['errmean']
        
        pl.add(centers,(cross-avgInputPower)/crossErr,label=polComb,color=col)


    pl.legendOn(labsize=10,loc='upper right')
    pl._ax.set_xlim(kellmin,kellmax)
    pl._ax.axhline(y=0.,ls="--",color='black',alpha=0.5)
    pl.done("tests/output/bias.png")


    # cross compared to theory (percent)
    pl = Plotter()

    for polComb,col in zip(polCombList,colorList):
        cross = statsCross[polComb]['mean']
        fp = interp1d(centers,cross,fill_value='extrapolate')
        
        pl.add(ellkk,(fp(ellkk)-Clkk)*100./Clkk,lw=2,label=polComb,color=col)


    pl.legendOn(labsize=10,loc='upper right')
    pl._ax.set_xlim(kellmin,kellmax)
    pl._ax.axhline(y=0.,ls="--",color='black',alpha=0.5)
    pl._ax.set_ylim(-10.,5.)
    pl.done("tests/output/percentTheory.png")



    # input power compared to theory (percent)
    pl = Plotter()

    fp = interp1d(centers,avgInputPower,fill_value='extrapolate')
        
    pl.add(ellkk,(fp(ellkk)-Clkk)*100./Clkk,lw=2)


    pl.legendOn(labsize=10,loc='upper right')
    pl._ax.set_xlim(kellmin,kellmax)
    pl._ax.axhline(y=0.,ls="--",color='black',alpha=0.5)
    pl._ax.set_ylim(-30.,30.)
    pl.done("tests/output/percentTheoryInput.png")



