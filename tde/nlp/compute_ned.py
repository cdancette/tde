#!/usr/bin/env python

import sys
import math
import os
import logging
import codecs
from itertools import combinations, count
import argparse
import ipdb


import numpy as np 
import pandas as pd
import editdistance # see (1)

#from utils import read_gold_phn, check_phn_boundaries, Stream_stats, nCr
from utils import *

import difflib
#from joblib import Parallel, delayed

# (1) I checked various edit-distance implementations (see https://github.com/aflc/editdistance)
# and I found that 'editdistance' gives the same result than our implementation of the
# distance (https://github.com/bootphon/tde, module tde.substrings.levenshtein) and it's a bit faster 

# load environmental varibles
try:
    PHON_GOLD=os.environ['PHON_GOLD']
except:
    print("PHON_GOLD not set")
    sys.exit

# if LOG environment doesnt exist then use the stderr  
try:
    LOG = os.environ['LOG_NED']
except:
    LOG = 'test.log' 

#LOG_LEV = logging.ERROR
LOG_LEV = logging.DEBUG
#LOG_LEV = logging.INFO

# configuration of logging
def get_logger(level=logging.WARNING):
    FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
    #logging.basicConfig(filename=LOG, format=FORMAT, level=LOG_LEV)
    logging.basicConfig(stream=sys.stdout, format=FORMAT, level=LOG_LEV)


def func_ned(s1, s2):
    return float(editdistance.eval(s1, s2)) / max(len(s1), len(s2))


def ned_from_class(classes_file, transcription, PHON_GOLD, verbose):
    '''compute the ned from the tde class file.'''
  
    # get logger
    if verbose:
        get_logger(level=logging.DEBUG)
    else:
        get_logger(level=logging.INFO)

    ## reading the phoneme gold
    phn_gold = PHON_GOLD 
    #gold, ix2symbols = read_gold_phn(phn_gold)
    # create interval tree for each filename in gold
    gold, trs, ix2symbols, symbol2ix = read_gold_intervals(phn_gold)

    
    # parsing the class file.
    # class file begins with the Class header,
    # following by a list of intervals and ending
    # by an space ... once the space is reached it
    # is possible to compute the ned within the class

    logging.info("NLP::NED : Parsing class file %s", classes_file)
    
    # initializing variables used on the streaming computations 
    classes = list()
    n_pairs = count() # used to debug
    total_expected_pairs = 0
    output_transcript = []

    # objects with the streaming statistics
    cross = Stream_stats()
    within = Stream_stats()
    overall = Stream_stats()

    # to compute NED you'll need the following steps:
    # 1. search for the pair of words the correponding 
    #    phoneme anotations.
    # 2. compute the Levenshtein distance between the two string.
    # 
    # see bellow 

    # file is decoded line by line and ned statistics are computed in 
    # a streaming to avoid using a high amount of memory
    with codecs.open(classes_file, encoding='utf8') as cfile:
        for lines in cfile:
            line = lines.strip()
            if len(line) == 0: 
                # empty line means that the class has ended and it is possilbe to compute ned
          
                # compute the theoretical number of pairs in each class.
                # remove from that count the pairs that were not found in the gold set.
                total_expected_pairs += nCr(len(classes), 2) 
                throwaway_pairs = 0
                
                # compute the ned for all combination of intervals without replacement 
                # in group of two
                for elem1, elem2 in combinations(range(len(classes)), 2):

                    # 1. search for the intevals in the phoneme file

                    # First interval from pair
                    fname1, on1, off1 = classes[elem1]
                    int1, t1 = get_intervals(fname1, float(on1), float(off1), gold, trs)
                    s1 = [symbol2ix[sym] for sym in t1]

                    
                    # Second interval from pair
                    fname2, on2, off2 = classes[elem2]
                    int2, t2 = get_intervals(fname2, float(on2), float(off2), gold, trs)
                    s2 = [symbol2ix[sym] for sym in t2]

                    ## get the phonemes (bugfix, don't take empty list if only 1 phone discovered)
                    #try:
                    #    s1 = gold[classes[elem1][0]]['phon'][b1_:e1_]# if e1_>b1_ \
                    #    #     else np.array([gold[classes[elem1][0]]['phon'][b1_]])
                    #    #if e1_ == b1_:
                    #    #    ipdb.set_trace()
                    #except:
                    #    # if detected phone is completely out of alignment

                    #    s1 = []
                    #try:
                    #    s2 = gold[classes[elem2][0]]['phon'][b2_:e2_]#  if e2_>b2_ \
                    #    #     else np.array([gold[classes[elem2][0]]['phon'][b2_]])
                    #    #if e2_==b2_:
                    #    #    ipdb.set_trace()
                    #except IndexError:
                    #    # if detected phone is completely out of alignment
                    #    s2 = []

                    # get transcription 
                    #t1 = [ix2symbols[sym] for sym in s1]
                    #t2 = [ix2symbols[sym] for sym in s2]

                    # if on or both of the word is not found in the gold, go to next pair  
                    if len(s1) == 0 and len(s2) == 0:
                        throwaway_pairs += 1
                        logging.debug("%s interv(%f, %f) and %s interv(%f, %f) not in gold", 
                                classes[elem1][0], classes[elem1][1], classes[elem1][2],
                                classes[elem2][0], classes[elem2][1], classes[elem2][2])
                        #neds_ = 1.0
                        continue
                  
                    if len(s1) == 0 or len(s2) == 0:
                        throwaway_pairs += 1
                        #neds_ = 1.0
                        if s1 == 0:
                            logging.debug("%s interv(%f, %f) not in gold",
                                    classes[elem1][0], classes[elem1][1], classes[elem1][2])
                        else:
                            logging.debug("%s interv(%f, %f) not in gold",
                                    classes[elem2][0], classes[elem2][1], classes[elem2][2])
                        continue
                    else:
                        # 2. compute the Levenshtein distance and NED
                        ned = func_ned(s1, s2)

                    # if requested, output the transcription of current pair, along with its ned
                    if transcription: 
                        output_transcript.append(u'{} {} {} {}\t{} {} {} {} {}'.format(classes[elem1][0], classes[elem1][1],
                                                                          classes[elem1][2], ','.join(t1).decode('utf8'),
                                                                          classes[elem2][0], classes[elem2][1],
                                                                          classes[elem2][2], ','.join(t2).decode('utf8'), ned))
                        #logging.debug(u'{} {} {} {}\t{} {} {} {} {}'.format(classes[elem1][0], classes[elem1][1],
                        #                                                  classes[elem1][2], ','.join(t1).decode('utf8'),
                        #                                                  classes[elem2][0], classes[elem2][1],
                        #                                                  classes[elem2][2], ','.join(t2).decode('utf8'), ned))

                    #python standard library difflib that is not the same that levenshtein
                    #it does not yield minimal edit sequences, but does tend to 
                    #yield matches that look right to people
                    # neds_ = 1.0 - difflib.SequenceMatcher(None, s1, s2).real_quick_ratio()
                    
                    # streaming statisitcs  
                    if classes[elem1][0] == classes[elem2][0]: # within 
                        within.add(ned)
                        
                    else: # cross speaker 
                        cross.add(ned)

                    # overall speakers = all the information
                    overall.add(ned)
                    
                    # it will show some work has been done ...
                    n_total = n_pairs.next()
                    if (n_total%1e6) == 0.0 and n_total>0:
                        logging.debug("NLP::NED : done %s pairs", n_total)

                # clean the varibles that contains the tokens
                total_expected_pairs -= throwaway_pairs
                classes = list()

            # if is found the label Class do nothing  
            elif line[:5] == 'Class': # the class + number + ngram if available
                pass
           
            # getting the information of the pairs
            else:
                fname, start, end = line.split(' ')
                classes.append([fname, float(start), float(end)])

    # logging the results
    #logging.info('overall: NED=%.2f std=%.2f pairs=%d (%d total pairs)', overall.mean(),
    #             overall.std(), overall.n(), total_expected_pairs) 
    #logging.info('cross: NED=%.2f std=%.2f pairs=%d', cross.mean(), 
    #             cross.std(), cross.n())
    #logging.info('within: NED=%.2f std=%.2f pairs=%d', within.mean(), 
    #             within.std(), within.n())
    return overall.mean(), cross.mean(), within.mean(), output_transcript


if __name__ == '__main__':

    command_example = '''example:
    
        compute_ned.py file.class

    '''
    parser = argparse.ArgumentParser(epilog=command_example)
    parser.add_argument('fclass', metavar='CLASS_FILE', nargs=1, \
            help='Class file in tde format')
    parser.add_argument('--transcription', action='store_true', \
            help='Enable to output complete transcription of pairs found')
    parser.add_argument('--PHON_GOLD', default=os.environ['PHON_GOLD'],
            help ='Path to the phone alignment')

    args = parser.parse_args()

    # TODO: check file
    disc_class = args.fclass[0]

    #get_logger(level=LOG_LEV)
    logging.info("Begining computing NED for %s", disc_class)
    ned_from_class(disc_class, args.transcription, PHON_GOLD)
    logging.info('Finished computing NED for %s', disc_class)

