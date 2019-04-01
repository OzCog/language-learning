import sys
import random

from linkgrammar import ParseOptions, Dictionary, Sentence, Linkage
from ..grammar_tester.psparse import parse_postscript
from ..common.optconst import *

__all__ = ['Evaluate_Alternative']

def Load_File(filename):
    """
        Loads a data file
    """
    with open(filename) as file:
        data = file.readlines()
    print("Finished loading")

    return data

def Get_Parses(data):
    """
        Reads parses from data, counting number of parses by newlines
        - sentences: list with tokenized sentences in data
        - parses: a list of lists containing the split links of each parse
        [
          [[link1-parse1][link2-parse1] ... ]
          [[link1-parse2][link2-parse2] ... ]
          ...
        ]
        Each list is splitted into tokens using space.
    """
    parses = []
    sentences = []
    parse_num = -1
    new_flag = True
    for line in data:
        if line == "\n":
            # get rid of sentences with no links
            new_flag = True
            continue
        if new_flag:
            new_flag = False
            sentences.append(line.split())
            parses.append([])
            parse_num += 1
            continue
        parses[parse_num].append(line.split())

    return parses, sentences

def MakeSets(parse, sent_len, ignore_WALL):
    """
        Gets a list with links and its sentence's length and returns a
        set of sets for each link's ids, ignoring WALL and dot if requested
    """
    current_ignored = 0
    link_list = []
    for link in parse:
        if ignore_WALL:
            if (link[0] == '0') or (link[2] == str(sent_len) and link[3] == "."):
                current_ignored += 1
                continue
        link_list.append([link[0], link[2]])

    # using sets for each link evaluates without link direction
    links_set = set(map(frozenset, link_list))
    return links_set, current_ignored

def Evaluate_Parses(test_parses, ref_parses, ref_sents, verbose, ignore):
    """
        Compares test_parses against ref_parses link by link
        counting errors
    """
    evaluated_parses = 0
    ignored_links = 0   # ignored links from ref, if ignore is active
    sum_precision = 0
    sum_recall = 0

    for ref_parse, test_parse, ref_sent in zip(ref_parses, test_parses, ref_sents):

        true_pos = 0
        false_neg = 0
        false_pos = 0

        # using sets to ignore link directions
        ref_sets, current_ignored = MakeSets(ref_parse, len(ref_sent), ignore)

        # if no links are left after ignore, skip parse
        if len(ref_sets) == 0:
            continue
        else:
            evaluated_parses += 1

        test_sets, dummy = MakeSets(test_parse, len(ref_sent), ignore)

        # if test_sets has no links left, precision and recall are zero
        if len(test_sets) == 0:
            continue

        # count current parse guesses
        true_pos = len(ref_sets.intersection(test_sets))
        false_neg = len(ref_sets) - true_pos
        false_pos = len(test_sets) - true_pos

        # update global counts
        ignored_links += current_ignored
        sum_precision += true_pos / (true_pos + false_pos)  # add parse's precision
        sum_recall += true_pos / (true_pos + false_neg)  # add parse's recall

        if verbose:
            print("Sentence: {}".format(" ".join(ref_sent)))
            print("Correct links: {}".format(true_pos))
            print("Missing links: {}".format(false_neg))
            print("Extra links: {}".format(false_pos))

    precision = sum_precision / evaluated_parses # averages precision
    recall = sum_recall / evaluated_parses # averages recall
    print("\nAvg Precision: {:.2%}".format(precision))
    print("Avg Recall: {:.2%}".format(recall))
    print("Avg Fscore: {:.2%}\n".format(2 * precision * recall / (precision + recall)))
    print("A total of {} parses evaluated, {:.2%} of reference file".format(evaluated_parses, float(evaluated_parses) / len(ref_parses)))
    print("{:.2f} ignored links per evaluated parse".format(ignored_links / evaluated_parses))
    
def Make_Sequential(sents):
    """
        Make sequential parses (each word simply linked to the next one), 
        to use as baseline
    """
    sequential_parses = []
    for sent in sents:
        parse = [["0", "###LEFT-WALL###", "1", sent[0]]] # include left-wall
        for i in range(1, len(sent)):
            parse.append([str(i), sent[i - 1], str(i + 1), sent[i]])
        #parse.append([str(i), sent[i - 1], str(i + 1), sent[i]] for i in range(1, len(sent)))
        sequential_parses.append(parse)

    return sequential_parses

def Make_Random(sents):
    """
        Make random parses (from LG-parser "any"), to use as baseline
    """
    any_dict = Dictionary('any') # Opens dictionary only once
    po = ParseOptions(min_null_count=0, max_null_count=999)
    po.linkage_limit = 100
    options = 0x00000000 | BIT_STRIP #| BIT_ULL_IN
    options |= BIT_CAPS

    random_parses = []
    for sent in sents:
        num_words = len(sent)
        curr_parse = []
        # subtitute words with numbers, as we only care about the parse tree
        fake_words = ["w{}".format(x) for x in range(1, num_words + 1)]
        # restore final dot to maintain --ignore functionality
        if sent[-1] == ".": 
            fake_words[-1] = "."
        sent_string = " ".join(fake_words)
        sentence = Sentence(sent_string, any_dict, po)
        linkages = sentence.parse()
        num_parses = len(linkages) # check nbr of linkages in sentence
        if num_parses > 0:
            idx = random.randint(0, num_parses - 1) # choose a random linkage index
            linkage = Linkage(idx, sentence, po._obj) # get the random linkage
            tokens, links = parse_postscript(linkage.postscript().replace("\n", ""), options)
            for link in links:
                llink = link[0]
                rlink = link[1]
                curr_parse.append([str(llink), tokens[llink], str(rlink), tokens[rlink]])

            random_parses.append(curr_parse)

    return random_parses

def Evaluate_Alternative(ref_file, test_file, verbose, ignore_WALL, sequential, random_flag):

    ref_data = Load_File(ref_file)
    ref_parses, ref_sents = Get_Parses(ref_data) 
    if sequential:
        test_parses = Make_Sequential(ref_sents)
    elif random_flag:
        test_parses = Make_Random(ref_sents)
    else:
        test_data = Load_File(test_file)
        test_parses, dummy = Get_Parses(test_data) 
    if len(test_parses) != len(ref_parses):
        sys.exit("ERROR: Number of parses differs in files: ", len(test_parses), ", ", len(ref_parses))
    Evaluate_Parses(test_parses, ref_parses, ref_sents, verbose, ignore_WALL)
