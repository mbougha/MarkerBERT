
import argparse
import nltk
from nltk.stem.porter import PorterStemmer
import time
import tensorflow as tf
import spacy as sp
from spacy.tokens import Doc
import copy

STRATEGIES = ('un_mark_pass', 'un_mark_pair', 'mu_mark_pass', 'mu_mark_pair', 'base')

def get_marker(strategy):
    strategy = strategy.lower()
    if strategy not in STRATEGIES:
        raise ValueError('strategy must be in ', STRATEGIES)
    if strategy == 'un_mark_pass':
        return UnPassMarker()
    if strategy == 'un_mark_pair':
        return UnPairMarker()
    if strategy == 'mu_mark_pass':
        return MuPassMarker()
    if strategy == 'mu_mark_pair':
        return MuPairMarker()
    if strategy == 'base':
        return BaseMarker()

class Marker(object):

    def __init__(self, stem=None):
        self.nlp = sp.load("en_core_web_sm", disable=['parser', 'tagger', 'ner'])
        self.nlp.max_length = 2100000
        if stem:
            self.stem = stem
        else:
            porter = PorterStemmer()
            self.stem = porter.stem
    def mark(self, *args, **kwds):
        """ mark """
        if len(args) == 2 :
            return self._mark(args[0], args[1])
        elif len(args) == 3:
            return self._mark_with_title(args[0], args[1], args[2])
        else :
            return None
    
    def _mark_with_title(self, query, title, doc):
        """ mark the pair of query (title,doc) or the (title,doc) only depending on the strategy"""
        raise NotImplementedError()

    def _mark(self, query, doc):
        """ mark the pair or the doc only depending on the strategy"""
        raise NotImplementedError()

class BaseMarker(Marker):

    def _mark(self,query,doc):
        return query,doc
    def _mark_with_title(self, query, title, doc):
        return query, title ,doc

class UnPassMarker(Marker):

    def __init__(self, stem=None):
        super(UnPassMarker, self).__init__(stem)
        self.query = ''
        self.stems = set()
        self.title = ''
        self.t = None
        self.title_terms = []

    def _mark(self, query, doc):
        d = self.nlp(doc)
        if query != self.query:
            self.query = query
            q = self.nlp(query)
            self.stems = set()
            for token in q:
                if not (token.is_punct or token.is_stop):
                    self.stems.add(self.stem(token.text.lower()))

        marked_doc = []
        
        for i,term in enumerate(d):
            marked_doc.append(term.text)
            if not (term.is_punct or term.is_stop):
                stem = self.stem(term.text.lower())
                for q_stem in self.stems:
                    if q_stem == stem:
                        marked_doc.pop()
                        marked_doc.append(f"#{term.text}#")
                        break                   
        doc = Doc(self.nlp.vocab, words=marked_doc, spaces=[token.whitespace_ for token in d])
        return query, ''.join(token.text_with_ws for token in doc)
    
    def _mark_with_title(self, query, title, doc):
        d = self.nlp(doc)
        if query != self.query:
            self.query = query
            q = self.nlp(query)
            self.stems = set()
            for token in q:
                if not (token.is_punct or token.is_stop):
                    self.stems.add(self.stem(token.text.lower()))
        if title != self.title:
            self.title = title
            self.t = self.nlp(title)
            self.title_terms = []
            for i,term in enumerate(self.t):
                self.title_terms.append(term.text)
                if not (term.is_punct or term.is_stop):
                    stem = self.stem(term.text.lower())
                    for q_stem in self.stems:
                        if q_stem == stem:
                            self.title_terms.pop()
                            self.title_terms.append(f"#{term.text}#")
                            break 
        marked_doc = []
        for i,term in enumerate(d):
            marked_doc.append(term.text)
            if not (term.is_punct or term.is_stop):
                stem = self.stem(term.text.lower())
                for q_stem in self.stems:
                    if q_stem == stem:
                        marked_doc.pop()
                        marked_doc.append(f"#{term.text}#")
                        break 
        title = Doc(self.nlp.vocab, words=self.title_terms, spaces=[token.whitespace_ for token in self.t])                  
        doc = Doc(self.nlp.vocab, words=marked_doc, spaces=[token.whitespace_ for token in d])
        return query, ''.join(token.text_with_ws for token in title), ''.join(token.text_with_ws for token in doc)

class UnPairMarker(Marker):

    def __init__(self, stem=None):
        super(UnPairMarker, self).__init__(stem)
        self.query = ''
        self.stems = set()
        self.query_terms = []
        self.q = None
        self.title = ''
        self.t = None
        self.title_terms = []
        self.mark_stem = dict()
    
    def _set_query_terms(self,terms_list):
        self.query_terms = []
        self.query_terms = copy.deepcopy(terms_list)

    def _get_query_terms(self):
        return copy.deepcopy(self.query_terms)

    def _mark(self, query, doc):
        d = self.nlp(doc)
        if query != self.query:
            self.query = query
            self.q = self.nlp(query)
            self.query_terms = []
            self.stems = dict()
            for i,token in enumerate(self.q):
                self.query_terms.append(token.text)
                if not (token.is_punct or token.is_stop):
                    stem = self.stem(token.text.lower())
                    self.stems[stem] = self.stems[stem]+[i] if stem in self.stems else [i]
        marked_q = self._get_query_terms()
        
        mark = dict ()
        marked_doc = []
        for i,term in enumerate(d):
            marked_doc.append(term.text)
            if not (term.is_punct or term.is_stop):
                stem = self.stem(term.text.lower())
                for q_stem in self.stems:
                    if q_stem == stem:
                        mark[q_stem] = True 
                        marked_doc.pop()
                        marked_doc.append(f"#{term.text}#")  
                        break              
                
        for stem in mark:
            for i in self.stems[stem]:
                marked_q[i] = f"#{marked_q[i]}#" 

        qu = Doc(self.nlp.vocab, words=marked_q, spaces= [token.whitespace_ for token in self.q])
        doc = Doc(self.nlp.vocab, words=marked_doc, spaces=[token.whitespace_ for token in d])
        return ''.join(token.text_with_ws for token in qu), ''.join(token.text_with_ws for token in doc)

    def _mark_with_title(self, query, title, doc):
        d = self.nlp(doc)
        if query != self.query:
            self.query = query
            self.q = self.nlp(query)
            self.query_terms = []
            self.stems = dict()
            for i,token in enumerate(self.q):
                self.query_terms.append(token.text)
                if not (token.is_punct or token.is_stop):
                    stem = self.stem(token.text.lower())
                    self.stems[stem] = self.stems[stem]+[i] if stem in self.stems else [i]
        marked_q = self._get_query_terms()

        if title != self.title:
            self.title = title
            self.t = self.nlp(title)
            self.title_terms = []
            self.mark_stem = dict()
            for i,term in enumerate(self.t):
                self.title_terms.append(term.text)
                if not (term.is_punct or term.is_stop):
                    stem = self.stem(term.text.lower())
                    for q_stem in self.stems:
                        if q_stem == stem:
                            self.mark_stem[q_stem] = True
                            self.title_terms.pop()
                            self.title_terms.append(f"#{term.text}#")
                            break 
        mark = copy.deepcopy(self.mark_stem)
        marked_doc = []
        for i,term in enumerate(d):
            marked_doc.append(term.text)
            if not (term.is_punct or term.is_stop):
                stem = self.stem(term.text.lower())
                for q_stem in self.stems:
                    if q_stem == stem:
                        mark[q_stem] = True 
                        marked_doc.pop()
                        marked_doc.append(f"#{term.text}#")  
                        break              
                
        for stem in mark:
            for i in self.stems[stem]:
                marked_q[i] = f"#{marked_q[i]}#" 

        title = Doc(self.nlp.vocab, words=self.title_terms, spaces=[token.whitespace_ for token in self.t])
        qu = Doc(self.nlp.vocab, words=marked_q, spaces= [token.whitespace_ for token in self.q])
        doc = Doc(self.nlp.vocab, words=marked_doc, spaces=[token.whitespace_ for token in d])
        return ''.join(token.text_with_ws for token in qu), ''.join(token.text_with_ws for token in title), ''.join(token.text_with_ws for token in doc)

class MuPassMarker(Marker):
    def __init__(self, stem=None):
        super(MuPassMarker, self).__init__(stem)
        self.query = ''
        self.stem_to_id = dict()
        self.title = ''
        self.t = None
        self.title_terms = []
    
    def _mark(self, query, doc):
        d = self.nlp(doc)
        if query != self.query:
            self.query = query
            q = self.nlp(query)
            self.stem_to_id = dict()
            q_i = 0
            for token in q:
                if not (token.is_punct or token.is_stop):
                    stem = self.stem(token.text.lower())
                    if stem not in self.stem_to_id :
                        self.stem_to_id[stem] = q_i
                        q_i +=1

        marked_doc = []
        for i,term in enumerate(d):
            marked_doc.append(term.text)
            if not (term.is_punct or term.is_stop):
                stem = self.stem(term.text.lower())
                for q_stem in self.stem_to_id:
                    if q_stem == stem:
                        q_i = self.stem_to_id[stem]
                        marked_doc.pop()
                        marked_doc.append(f"[e{q_i}]{term.text}[\e{q_i}]")
                        break                   
        
        doc = Doc(self.nlp.vocab, words=marked_doc, spaces=[token.whitespace_ for token in d])
        return query, ''.join(token.text_with_ws for token in doc)

    def _mark_with_title(self, query, title, doc):
        d = self.nlp(doc)
        if query != self.query:
            self.query = query
            q = self.nlp(query)
            self.stem_to_id = dict()
            q_i = 0
            for token in q:
                if not (token.is_punct or token.is_stop):
                    stem = self.stem(token.text.lower())
                    if stem not in self.stem_to_id :
                        self.stem_to_id[stem] = q_i
                        q_i +=1
        if title != self.title:
            self.title = title
            self.t = self.nlp(title)
            self.title_terms = []
            for i,term in enumerate(self.t):
                self.title_terms.append(term.text)
                if not (term.is_punct or term.is_stop):
                    stem = self.stem(term.text.lower())
                    for q_stem in self.stem_to_id:
                        if q_stem == stem:
                            q_i = self.stem_to_id[stem]
                            self.title_terms.pop()
                            self.title_terms.append(f"[e{q_i}]{term.text}[\e{q_i}]")
                            break  
        marked_doc = []
        for i,term in enumerate(d):
            marked_doc.append(term.text)
            if not (term.is_punct or term.is_stop):
                stem = self.stem(term.text.lower())
                for q_stem in self.stem_to_id:
                    if q_stem == stem:
                        q_i = self.stem_to_id[stem]
                        marked_doc.pop()
                        marked_doc.append(f"[e{q_i}]{term.text}[\e{q_i}]")
                        break                   
        tit = Doc(self.nlp.vocab, words=self.title_terms, spaces=[token.whitespace_ for token in self.t])
        doc = Doc(self.nlp.vocab, words=marked_doc, spaces=[token.whitespace_ for token in d])
        return query, ''.join(token.text_with_ws for token in tit), ''.join(token.text_with_ws for token in doc)

class MuPairMarker(Marker):
    def __init__(self, stem=None):
        super(MuPairMarker, self).__init__(stem)
        self.query = ''
        self.stem_to_id = dict()
        self.id_to_pos = dict()
        self.q = None
        self.query_terms = []
        self.title = ''
        self.t = None
        self.title_terms = []
        self.mark_stem = set()
    
    def _get_query_terms(self):
        return copy.deepcopy(self.query_terms)
    
    def _mark(self, query, doc):
        d = self.nlp(doc)
        if query != self.query:
            self.query = query
            self.q = self.nlp(query)
            self.stem_to_id = dict()
            self.id_to_pos = dict()
            self.query_terms = []
            q_i = 0
            for pos, token in enumerate(self.q):
                self.query_terms.append(token.text)
                if not (token.is_punct or token.is_stop):
                    stem = self.stem(token.text.lower())
                    if stem in self.stem_to_id :
                        i = self.stem_to_id[stem]
                        self.id_to_pos[i]= self.id_to_pos[i]+[pos]
                    if stem not in self.stem_to_id :
                        self.stem_to_id[stem] = q_i
                        self.id_to_pos[q_i] = [pos]
                        q_i +=1
        marked_q = self._get_query_terms()
        mark = set()
        marked_doc = []      
        for i,term in enumerate(d):
            marked_doc.append(term.text)
            if not (term.is_punct or term.is_stop):
                stem = self.stem(term.text.lower())
                for q_stem in self.stem_to_id:
                    if q_stem == stem:
                        q_i = self.stem_to_id[stem]
                        mark.add(q_i)
                        marked_doc.pop()
                        marked_doc.append(f"[e{q_i}]{term.text}[\e{q_i}]")
                        break  
        for i in mark:
            for pos in self.id_to_pos[i]:
                marked_q[pos] = f"[e{i}]{marked_q[pos]}[\e{i}]"

        qu = Doc(self.nlp.vocab, words=marked_q, spaces= [token.whitespace_ for token in self.q])    
        doc = Doc(self.nlp.vocab, words=marked_doc, spaces=[token.whitespace_ for token in d])
        return ''.join(token.text_with_ws for token in qu),''.join(token.text_with_ws for token in doc)
    
    def _mark_with_title(self, query, title, doc):
        d = self.nlp(doc)
        if query != self.query:
            self.query = query
            self.q = self.nlp(query)
            self.stem_to_id = dict()
            self.id_to_pos = dict()
            self.query_terms = []
            q_i = 0
            for pos, token in enumerate(self.q):
                self.query_terms.append(token.text)
                if not (token.is_punct or token.is_stop):
                    stem = self.stem(token.text.lower())
                    if stem in self.stem_to_id :
                        i = self.stem_to_id[stem]
                        self.id_to_pos[i]= self.id_to_pos[i]+[pos]
                    if stem not in self.stem_to_id :
                        self.stem_to_id[stem] = q_i
                        self.id_to_pos[q_i] = [pos]
                        q_i +=1
        marked_q = self._get_query_terms()
        if title != self.title:
            self.title = title
            self.t = self.nlp(title)
            self.title_terms = []
            self.mark_stem = set()
            for i,term in enumerate(self.t):
                self.title_terms.append(term.text)
                if not (term.is_punct or term.is_stop):
                    stem = self.stem(term.text.lower())
                    for q_stem in self.stem_to_id:
                        if q_stem == stem:
                            q_i = self.stem_to_id[stem]
                            self.mark_stem.add(q_i)
                            self.title_terms.pop()
                            self.title_terms.append(f"[e{q_i}]{term.text}[\e{q_i}]")
                            break 
        mark = copy.deepcopy(self.mark_stem)
        marked_doc = []      
        for i,term in enumerate(d):
            marked_doc.append(term.text)
            if not (term.is_punct or term.is_stop):
                stem = self.stem(term.text.lower())
                for q_stem in self.stem_to_id:
                    if q_stem == stem:
                        q_i = self.stem_to_id[stem]
                        mark.add(q_i)
                        marked_doc.pop()
                        marked_doc.append(f"[e{q_i}]{term.text}[\e{q_i}]")
                        break  
        for i in mark:
            for pos in self.id_to_pos[i]:
                marked_q[pos] = f"[e{i}]{marked_q[pos]}[\e{i}]"

        qu = Doc(self.nlp.vocab, words=marked_q, spaces= [token.whitespace_ for token in self.q]) 
        tit = Doc(self.nlp.vocab, words=self.title_terms, spaces=[token.whitespace_ for token in self.t])   
        doc = Doc(self.nlp.vocab, words=marked_doc, spaces=[token.whitespace_ for token in d])
        return ''.join(token.text_with_ws for token in qu), ''.join(token.text_with_ws for token in tit), ''.join(token.text_with_ws for token in doc)


