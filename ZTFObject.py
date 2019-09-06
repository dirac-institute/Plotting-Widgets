from collections import OrderedDict
import ipywidgets as w
import pandas as pd
#from couchbase.cluster import Cluster, PasswordAuthenticator
#from couchbase.n1ql import N1QLQuery
import gzip
import io
import os
import base64
from astropy.io import fits
from PIL import Image
import numpy as np

# use hbase to encode byte strings from kafka as base64 endoded strings
def encodeImage(buffer):
    '''Encode a byte array as base64 string'''
    return base64.b64encode(buffer).decode('ascii')
    
def decodeImage(string):
    '''Decode a string array into byte array using base64'''
    return base64.b64decode(string)

def blank_image():
    output = io.BytesIO()
    image_layout=w.Layout(object_fit='cover', width="40%")
    
    im = 10.*np.random.rand(15,15)
    im = Image.fromarray(im)
    im = im.convert('RGB')
    #save as btye array and read into widget
    im.save(output, format='PNG')
    return w.Image(value=output.getvalue(),format='png',layout=image_layout)

import operator
from functools import reduce

def equalize(im):
    h = im.convert("L").histogram()
    lut = []
    for b in range(0, len(h), 256):
        # step size
        step = reduce(operator.add, h[b:b+256]) / 255
        # create equalization lookup table
        n = 0
        for i in range(256):
            lut.append(n / step)
            n = n + h[i+b]
    # map image through lookup table
    return im.point(lut*3)


def create_widget(result):
    '''Generate image widget from couchbase return'''
    diffImage = decodeImage(result['differenceImage'])
    sciImage = decodeImage(result['scienceImage'])
    templateImage = decodeImage(result['templateImage'])

    #read as fits file from byte array 
    outputArray = []
    imageArray = [diffImage, sciImage, templateImage]
    
    
    image_layout=w.Layout(object_fit='cover', width="40%")
    for image in imageArray:
        with gzip.open(io.BytesIO(image), 'rb') as f:
            with fits.open(io.BytesIO(f.read())) as hdul:
                output = io.BytesIO()
                #convert to image (RGB)
                data = np.uint8(255 * (hdul[0].data - hdul[0].data.min()) / (hdul[0].data.max() - hdul[0].data.min()))
                im = Image.fromarray(hdul[0].data)
                im = im.convert('RGB')
                im = equalize(im)
                #save as bye array and read into widget
                im.save(output, format='PNG')
        outputArray.append(w.Image(value=output.getvalue(),format='png',layout=image_layout))
    return outputArray

class ZTF_lightcurve():
    def __init__(self, objectId, dbcon, image=False, couchbase=None):
        '''PLACEHOLDER for ZTFObject Class'''
        self.filterDict = OrderedDict({"g":1, "r":2, "i":3})
        
        #query data base and merge with zeropoint table
        data = pd.read_sql_query("SELECT pid, objectId, jd, magpsf, sigmapsf, magnr, sigmagnr, \
        isdiffpos, diffmaglim ,magzpsci, ra, decl, fid, classtar, rb, \
        candid, programid FROM alerts where objectId='{}' ORDER BY jd".format(objectId), con=dbcon)

        #TODO apply seropoints
        #dd = apply_zeropoint(zp_table, data)

        #load data and index to the individual passband fluxs 
        self.time = data.jd
        self.sigmapsf = data.sigmapsf
        self.diffmaglim = data.diffmaglim
        self.magpsf = data.magpsf
        self.magzpsci = data.magzpsci
        self.ra = data.ra
        self.decl = data.decl
        self.fid = data.fid
        self.candid = data.candid
        self.objectId = data.objectId[0]
        #self.dc_mag = dd['dc_mag']
        #self.dc_sigmag = dd['dc_sigmag']

        
        self.g = data.index[data.fid==1]
        self.r = data.index[data.fid==2]
        self.i = data.index[data.fid==3]
        
        self.diffImageArray = []
        self.templateImageArray = []
        self.scienceImageArray = []

        if (image == True):
            self.read_couchbase_objectId(couchbase)

    def read_couchbase_objectId(self, couchbase_bucket):
        '''Get images based on ZTF objectId'''
        #extract images - if no image present create a blank image
        i=0
        for candid in self.candid:
            try:
                result = couchbase_bucket.get('{}'.format(candid)).value
                diff, sci, temp =  create_widget(result)
                self.diffImageArray.append(diff)
                self.templateImageArray.append(sci)
                self.scienceImageArray.append(temp)
                #print (candid)
                i=i+1
            except Exception as ex:
                template = "An exception of type {0} occurred. Arguments:\n{1!r}"
                message = template.format(type(ex).__name__, ex.args)
                #print (message)
                blank = blank_image()
                self.diffImageArray.append(blank)
                self.templateImageArray.append(blank)
                self.scienceImageArray.append(blank)
        print('Number of points with images {}'.format(i))

    def apply_zeropoint(self, zp_table, lc):
        dflc = pd.merge(zp_table, lc, on=['pid'], how='inner')
        # LC: the light curve of your interest
        # here we just want to find "magzpsci" and "magzpsciunc" values if they are not available in the ZTF alert DB  
        # using " pabszp" and "pabszpunc" values in the Eric's ZP table.
        #---------------------------------
        dflc["magzpsci"] = dflc["pabszp"]
        dflc["magzpsciunc"] = dflc["pabszpunc"]

        dflc['sign'] = 2* (dflc['isdiffpos'] == 't') - 1
        dflc['ref_flux'] = 10**( 0.4* ( dflc['magzpsci'] - dflc['magnr']) )  

        dflc['ref_sigflux'] = dflc['sigmagnr']/1.0857*dflc['ref_flux']

        dflc['difference_flux'] = 10**( 0.4* ( dflc['magzpsci'] - dflc['magpsf']) )
        dflc['difference_sigflux'] = dflc['sigmapsf']/1.0857*dflc['difference_flux']


        dflc['dc_flux'] = dflc['ref_flux'] + dflc['sign']*dflc['difference_flux']  
        w = dflc['difference_sigflux'] > dflc['ref_sigflux']
        dflc.loc[w,'dc_sigflux'] =  np.sqrt( dflc.loc[w,'difference_sigflux']**2 - dflc.loc[w,'ref_sigflux']**2 )
        dflc.loc[~w,'dc_sigflux'] =  np.sqrt( dflc.loc[~w,'difference_sigflux']**2 + dflc.loc[~w,'ref_sigflux']**2 )

        dflc['dc_mag'] = dflc['magzpsci'] - 2.5 * np.log10(dflc['dc_flux'])
        dflc['dc_sigmag'] = dflc['dc_sigflux']/dflc['dc_flux']*1.0857
        return dflc
