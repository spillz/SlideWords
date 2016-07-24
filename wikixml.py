#!/bin/python
'''
wikixml.py

Module is used to build a frequency distribution of usage for the scrabble dictionary using a
wikipedia dump. The wikipedia dump can be found at: https://dumps.wikimedia.org/ 
(select enwiki and download "all pages, current versions only")
'''

import xml.etree.ElementTree as etree
import bz2
import re
import cPickle


wikipedia_dump_path = '' 
if wikipedia_dump_path == '':
    print 'you must edit the wikipedia_dump_path'
    import sys
    sys.exit()

def build_freq(filename, limit = -1):
    words = set(file("TWL06.txt","r").read().splitlines())

    freq = dict.fromkeys(words, 0)
    xml = bz2.BZ2File(wikipedia_dump_path)
    i = 0
    matches = 0
    
    
    # get an iterable
    context = etree.iterparse(xml, events=("start", "end"))

    # turn it into an iterator
    context = iter(context)

    # get the root element
    event, root = context.next()
    
    #for event, elem in etree.iterparse(xml, events=('start', 'end', 'start-ns', 'end-ns')):
    for event, elem in context:
        if event == 'end' and elem.tag.endswith('text'):
            text = etree.tostring(elem).upper()
            word_list = re.sub(r"\{\{.*?\}\}","", text, flags = re.DOTALL)
            #word_list = re.sub(r"\[\[(.*?)\|.*?\]\]",r" \1 ", word_list, flags = re.DOTALL)
            word_list = re.sub(r"\[\[.*?\]\]",r"", word_list, flags = re.DOTALL)
            word_list = re.sub(r"\<.*?\>","", word_list, flags = re.DOTALL)
            word_list = re.sub(r"\[.*?\]","", word_list, flags = re.DOTALL)
            word_list = re.sub(r"&LT;.*?&GT;","", word_list, flags = re.DOTALL)
            word_list = re.sub(r"&.*?;","", word_list, flags = re.DOTALL)
            word_list = re.sub("[^\w]", " ",  word_list).split()
            for w in word_list:
                try:
                    freq[w] += 1
                    matches += 1
                except KeyError:
                    pass
        i+=1
        if i%10000 == 0:
            print '%i records parsed, %i matches'%(i, matches)
            print elem.tag
        if i%1000000 == 0:
            cPickle.dump((freq, i), open(filename+'tmp', 'wb'))
        root.clear()
        if limit>0 and i>limit:
            break

    cPickle.dump(freq, open(filename, 'wb'))
    return freq

def load_freq(filename):
    return cPickle.load(open(filename, 'rb'))
        
def get_counts(freq):
    counts = dict.fromkeys([0.0,0.000001,0.00001,0.0001,0.001,0.01,0.05,0.1], 0)
    count = sum(freq.itervalues())
    words = len(freq)
    for f in freq:
        for c,v in counts.iteritems():
            if 1.0*freq[f]/count>=c:
                counts[c]+=1
    return words, count,counts

def print_top(freq, num):
    import operator
    sorted_freq = sorted(freq.items(), key=operator.itemgetter(1))
    for k,v in sorted_freq[-num:]:
        print k,v
    
#build_freq('word_freq1m.pck',1000000)
#
#words, count, counts = get_counts(load_freq('word_freq1m.pck'))        
#print 'total words', words
#print 'total hits', count
#print 'total counts', 
#for c,v in [(c,counts[c]) for c in sorted(counts)]:
#    print c,v
#print 'Top 100 words'
#print_top(load_freq('word_freq1m.pck'), 100)
    
build_freq('word_freq.pck')

words, count, counts = get_counts(load_freq('word_freq.pck'))        
print 'total words', words
print 'total hits', count
print 'total counts', 
for c,v in [(c,counts[c]) for c in sorted(counts)]:
    print c,v
print 'Top 100 words'
print_top(load_freq('word_freq.pck'), 100)

