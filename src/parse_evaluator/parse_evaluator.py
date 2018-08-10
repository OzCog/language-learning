#!/usr/bin/env python

# ASuMa, Mar 2018
# Read parse data in MST-parser format, from reference and test files
# and evaluate the accuracy of the test parses.
# See main() documentation below for usage details

import platform
import getopt, sys

def version():
    """
        Prints Python version used
    """
    print("Code writen for Python3.6.4. Using: %s"%platform.python_version())

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

def main(argv):
    """
        Evaluates parses compared to given reference.
        For each parse, loops through all links in reference and checks if those
        2 word-instances are also connected in parse to evaluate.

        Parses must be in format:
        Sentence to evaluate
        # word1 # word2
        # word2 # word3
        ...

        Another sentence to evaluate
        # word1 # word2
        ...

        Usage: ./parse_evaluator.py -t <testfile> -r <reffile> [-v] [-i]

        testfile        file with parses to evaluate
        goldfile        file with reference (gold standard) parses
        -v              verbose
        -i              don't ignore LEFT-WALL and end-of-sentence dot, if any
        -s              evaluate sequential parses (benchmark)

    """

    version()

    test_file = ''
    ref_file = ''
    verbose = False
    ignore_WALL = True
    sequential = False

    try:
        opts, args = getopt.getopt(argv, "ht:r:vis", ["test=", "reference=", "verbose", "ignore", "sequential"])
    except getopt.GetoptError:
        print("Usage: ./parse_evaluator.py -r <reffile> -t <testfile> [-v] [-i] [-s]")
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print("Usage: ./parse_evaluator.py -r <reffile> -t <testfile> [-v] [-i] [-s]")
            sys.exit()
        elif opt in ("-t", "--test"):
            test_file = arg
        elif opt in ("-r", "--reference"):
            ref_file = arg
        elif opt in ("-v", "--verbose"):
            verbose = True
        elif opt in ("-i", "--ignore"):
            ignore_WALL = False
        elif opt in ("-s", "--sequential"):
            sequential = True

    ref_data = Load_File(ref_file)
    ref_parses, ref_sents = Get_Parses(ref_data) 
    if sequential:
        test_parses = Make_Sequential(ref_sents)
    else:
        test_data = Load_File(test_file)
        test_parses, dummy = Get_Parses(test_data) 
    if len(test_parses) != len(ref_parses):
        sys.exit("ERROR: Number of parses differs in files")
    # for rs, ts in zip(ref_sents, dummy):
    #     print("Sentence pair:")
    #     print(rs, ts)
    Evaluate_Parses(test_parses, ref_parses, ref_sents, verbose, ignore_WALL)

def Make_Sequential(sents):
    """
        Make sequential parses (each word simply linked to the next one), 
        to use as a benchmark
    """
    sequential_parses = []
    for sent in sents:
        parse = [["0", "###LEFT-WALL###", "1", sent[0]]] # include left-wall
        for i in range(1, len(sent)):
            parse.append([str(i), sent[i - 1], str(i + 1), sent[i]])
        #parse.append([str(i), sent[i - 1], str(i + 1), sent[i]] for i in range(1, len(sent)))
        sequential_parses.append(parse)

    return sequential_parses


if __name__ == '__main__':
    main(sys.argv[1:])