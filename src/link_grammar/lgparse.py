"""
    This module is common for multiple Link Grammar parse scripts. 
        It exports:
            parse_file_with_api()   - function capable of parsing text files and calculating parse statistics.
            parse_corpus_files()    - function capable of traversing directory tree parsing each file.
"""
import sys
import re
import os
import shutil
from linkgrammar import LG_Error, Sentence, ParseOptions, Dictionary
from subprocess import Popen, PIPE

__all__ = ['parse_corpus_files', 'parse_file_with_api', 'parse_file_with_lgp', 'parse_batch_ps_output',
           'LG_DICT_PATH', 'BIT_CAPS', 'BIT_RWALL', 'BIT_STRIP', 'BIT_OUTPUT', 'BIT_ULL_IN', 'BIT_RM_DIR',
           'BIT_OUTPUT_DIAGRAM', 'BIT_OUTPUT_POSTSCRIPT', 'BIT_OUTPUT_CONST_TREE', 'BIT_OUTPUT_ALL',
           'BIT_BEST_LINKAGE', 'BIT_DPATH_CREATE', 'BIT_LG_EXE', 'traverse_dir', 'create_dir',
           ]

__version__ = "2.1.0"

LG_DICT_PATH = "/usr/local/share/link-grammar"

BIT_CAPS  = 0x001           # Keep capitalized letters in tokens
BIT_RWALL = 0x002           # Keep RIGHT-WALL tokens and the links
BIT_STRIP = 0x004           # Strip off token suffixes
BIT_OUTPUT= 0x038           # Output format
BIT_ULL_IN= 0x040           # If set parse_file_with_api() is informed that ULL parses are used as input, so only
                            #   sentences should be parsed, links should be filtered out.
BIT_RM_DIR= 0x080           # Remove grammar dictionary if it already exists. Then recreate it from scratch.
BIT_BEST_LINKAGE = 0x0100   # Take most probable linkage.
BIT_DPATH_CREATE = 0x0200   # Recreate dictionary path instead of source path
BIT_LG_EXE= 0x300           # Use link-parser executable in a separate process for parsing

# Output format constants. If no bits set ULL defacto format is used.
BIT_OUTPUT_DIAGRAM = 0x08
BIT_OUTPUT_POSTSCRIPT = 0x10
BIT_OUTPUT_CONST_TREE = 0x20
BIT_OUTPUT_ALL = BIT_OUTPUT_DIAGRAM | BIT_OUTPUT_POSTSCRIPT | BIT_OUTPUT_CONST_TREE


class LGParseError(Exception):
    pass

def strip_token(token) -> str:
    """
    Strip off suffix substring
    :param token: token string
    :return: stripped token if a suffix found, the same token otherwise
    """
    if token.startswith(".") or token.startswith("["):
        return token

    pos = token.find("[")

    # If "." is not found
    if pos < 0:
        pos = token.find(".")

        # If "[" is not found or token starts with "[" return token as is.
        if pos <= 0:
            return token

    return token[:pos:]


def parse_tokens(txt, opt) -> list:
    """
    Parse string of tokens
    :param txt: string token line extracted from postfix notation output string returned by Linkage.postfix()
            method.
    :param opt: bit mask option value (see parse_test() description for more details)
    :return: list of tokes
    """
    toks = []
    start_pos = 1
    end_pos = txt.find(")")

    while end_pos - start_pos > 0:
        token = txt[start_pos:end_pos:]

        if opt & BIT_STRIP == BIT_STRIP:
            token = strip_token(token)

        if token.find("-WALL") > 0:
            token = "###" + token + "###"
        else:
            if opt & BIT_CAPS == 0:
                token = token.lower()

        if token.find("RIGHT-WALL") < 0:
            toks.append(token)
        elif opt & BIT_RWALL == BIT_RWALL:
            toks.append(token)

        start_pos = end_pos + 2
        end_pos = txt.find(")", start_pos)

    return toks


def calc_stat(toks) -> (int, int, float):
    """
    Calculate percentage of successfully linked tokens. Token in square brackets considered to be unlinked.

    :param toks: List of tokens.
    :return: Tuple (int, int, float):
                - 1 if all tokens are linked, 0 otherwise;
                - 1 if all tokens are unlinked, 1 otherwise;
                - Percentage of successfully parsed tokens.
    """
    # Nothing to calculate if no tokens found
    if len(toks) == 0:
        return 0.0

    total = 0

    # Initialize number of unlinked tokens
    unlinked = 0

    # We assume that all tokens included in square brackets are unlinked
    for token in toks:
        # Exclude walls from statistics estimation
        if token.find("WALL") < 0:
            if token.startswith("["):
                unlinked += 1
            total += 1

    return unlinked == 0, total == unlinked, 1.0 if unlinked == 0 else 1.0 - float(unlinked) / float(total)


def parse_links(txt, toks) -> list:
    """
    Parse links represented in postfix notation and prints them in OpenCog notation.

    :param txt: link list in postfix notation
    :param toks: list of tokens previously extracted from postfix notated output
    :return: List of links in ULL format
    """
    links = []
    token_count = len(toks)
    start_pos = 1
    end_pos = txt.find("]")

    q = re.compile('(\d+)\s(\d+)\s\d+\s\(.+\)')

    while end_pos - start_pos > 0:
        mm = q.match(txt[start_pos:end_pos:])

        if mm is not None:
            index1 = int(mm.group(1))
            index2 = int(mm.group(2))

            if index2 < token_count:
                links.append((index1, toks[index1], index2, toks[index2]))

        start_pos = end_pos + 2
        end_pos = txt.find("]", start_pos)

    return links


def print_output(tokens, links, ofl):
    """
    Print links in ULL format to the output specified by 'ofl' variable.

    :param tokens: List of tokens.
    :param links: List of links.
    :param ofl: Output file handle.
    :return:
    """
    for token in tokens[1:]:
        ofl.write(token + ' ')

    ofl.write('\n')

    for link in links:
        print(link[0], link[1], link[2], link[3], file=ofl)

    print('', file=ofl)


def parse_postscript(text, options, ofile) -> (int, int, float):
    """
    Parse postscript notation of the linkage.

    :param text: text string returned by Linkage.postscript() method.
    :param ofile: output file object refference
    :return: Tuple (int, int, float):
                - Number of successfully parsed linkages;
                - Number of completely unparsed linkages;
                - Average value of successfully linked tokens.
    """

    p = re.compile('\[(\(LEFT-WALL\).+?)\]\[(.*?)\]\[0\]', re.S)
    m = p.match(text)

    # print(text)

    if m is not None:
        # print(m.group(1))
        tokens = parse_tokens(m.group(1), options)
        links = parse_links(m.group(2), tokens)
        # print(tokens)
        # print(links)
        sorted_links = sorted(links, key=lambda x: (x[0], x[2]))

        if not (options & BIT_OUTPUT):
            print_output(tokens, sorted_links, ofile)

        return calc_stat(tokens)

    return 0, 0, 0.0

def get_output_suffix(options) -> str:
    """ Return output file name suffix depending on set options """

    out_format = options & BIT_OUTPUT

    suff = "2" if (options & BIT_LG_EXE) else ""

    if (out_format & BIT_OUTPUT_CONST_TREE) == BIT_OUTPUT_CONST_TREE:
        return ".tree" + suff
    elif (out_format & BIT_OUTPUT_DIAGRAM) == BIT_OUTPUT_DIAGRAM:
        return ".diag" + suff
    elif (out_format & BIT_OUTPUT_POSTSCRIPT) == BIT_OUTPUT_POSTSCRIPT:
        return ".post" + suff
    else:
        return ".ull" + suff

def parse_file_with_api(dict_path, corpus_path, output_path, linkage_limit, options) \
        -> (float, float, float):
    """
    Link parser invocation routine.

    :param dict_path: name or path to the dictionary
    :param corpus_path: path to the test text file
    :param output_path: output file path
    :param linkage_limit: maximum number of linkages LG may return when parsing a sentence
    :param options: bit field. Use bit mask constants to set or reset one or multiple bits:
                BIT_CAPS  = 0x01    Keep capitalized letters in tokens untouched if set,
                                    make all lowercase otherwise.
                BIT_RWALL = 0x02    Keep all links with RIGHT-WALL if set, ignore them otherwise.
                BIT_STRIP = 0x04    Strip off token suffixes if set, remove them otherwise.
    :return: tuple (float, float, float):
                - percentage of totally parsed sentences;
                - percentage of completely unparsed sentences;
                - percentage of parsed sentences;
    """

    input_file_handle = None
    output_file_handle = None

    # Sentence statistics variables
    sent_full = 0                   # number of fully parsed sentences
    sent_none = 0                   # number of completely unparsed sentences
    sent_stat = 0.0                 # average value of parsed sentences (linkages)

    line_count = 0                  # number of sentences in the corpus

    print("Info: Parsing a corpus file: '" + corpus_path + "'")
    print("Info: Using dictionary: '" + dict_path + "'")

    if output_path is not None:
        print("Info: Parses are saved in: '" + output_path+get_output_suffix(options) + "'")
    else:
        print("Info: Output file name is not specified. Parses are redirected to 'stdout'.")

    try:
        link_line = re.compile(r"\A[0-9].+")

        po = ParseOptions(min_null_count=0, max_null_count=999)
        po.linkage_limit = linkage_limit

        di = Dictionary(dict_path)

        input_file_handle = open(corpus_path)
        output_file_handle = sys.stdout if output_path is None else open(output_path+get_output_suffix(options), "w")

        for line in input_file_handle:

            # Filter out links when ULL parses are used as input
            if options & BIT_ULL_IN > 0 and link_line.match(line):
                continue

            # Skip empty lines to get proper statistics estimation and skip commented lines
            if len(line.strip()) < 1 or line.startswith("#"):
                continue

            sent = Sentence(line, di, po)
            linkages = sent.parse()

            # Number of linkages taken in statistics estimation
            linkage_countdown = 1

            temp_full = 0
            temp_none = 0
            temp_stat = 0.0

            for linkage in linkages:

                if (options & BIT_OUTPUT_DIAGRAM) == BIT_OUTPUT_DIAGRAM:
                    print(linkage.diagram(), file=output_file_handle)

                elif (options & BIT_OUTPUT_POSTSCRIPT) == BIT_OUTPUT_POSTSCRIPT:
                    print(linkage.postscript(), file=output_file_handle)

                elif (options & BIT_OUTPUT_CONST_TREE) == BIT_OUTPUT_CONST_TREE:
                    print(linkage.constituent_tree(), file=output_file_handle)

                # It's not only parses postscript notated linkage output,
                #   but calculates statistics as well.
                (f, n, s) = parse_postscript(linkage.postscript().replace("\n", ""), options, output_file_handle)

                if linkage_countdown:
                    temp_full += f
                    temp_none += n
                    temp_stat += s
                    linkage_countdown -= 1

            if len(linkages) > 0:
                sent_full += temp_full
                sent_none += temp_none
                sent_stat += temp_stat / float(len(linkages))
            else:
                sent_none += 1

            line_count += 1

        # Prevent interleaving "Dictionary close" messages
        ParseOptions(verbosity=0)

    except LG_Error as err:
        print(str(err))

    except IOError as err:
        print(str(err))

    except FileNotFoundError as err:
        print(str(err))

    finally:
        if input_file_handle is not None:
            input_file_handle.close()

        if output_file_handle is not None and output_file_handle != sys.stdout:
            output_file_handle.close()

        return (0.0, 0.0, 0.0) if line_count == 0 else (float(sent_full) / float(line_count),
                                                        float(sent_none) / float(line_count),
                                                        sent_stat / float(line_count))


def traverse_dir(root, file_ext, on_file, on_dir=None, is_recursive=False):
    """
    Traverse directory tree and call callback functions for each file and subdirectory.
    :param root: Root directory to start traversing from.
    :param file_ext: File extention to filter files by type.
    :param on_file: callback function pointer to be called each time the file is found.
    :param on_dir: callback function pointer to be called each time the folder is found.
    :param is_recursive: Tells the function to recursively traverse directory tree if set to True, otherwise False.
    :return:
    """
    for entry in os.scandir(root):

        if entry.is_dir():
            is_traversing = is_recursive

            if on_dir is not None:
                is_traversing = (is_traversing and on_dir(entry.path))

            if is_traversing:
                traverse_dir(entry.path, file_ext, on_file, on_dir, True)

        elif entry.is_file() and (len(file_ext) < 1 or (len(file_ext) and entry.path.endswith(file_ext))):
            if on_file is not None:
                try:
                    on_file(entry.path)
                except LGParseError as err:
                    print("LGParseError: " + str(err))


def get_dir_name(file_name) -> (str, str):
    """
    Extract template grammar directory name and a name for new grammar directory

    :param file_name: Grammar file name. It should have the following notation:

                '<grammar-name>_<N>C_<yyyy-MM-dd>_<hhhh>.4.0.dict' (e.g. poc-turtle_8C_2018-03-03_0A10.4.0.dict)

                          grammar-name      Name of the language the grammar file was created for
                          N                 Number of clusters used while creating the grammar followed by literal 'C'.
                          yyyy-MM-dd        Dash delimited date, where yyyy - year (e.g. 2018), MM - month,
                                            dd - day of month.
                          hhhh              Hexadecimal sequential number.

                          4.0.dict suffix is mandatory for any grammar definition file and should not be ommited.

    :return: tuple (template_grammar_directory_name, grammar_directory_name)
    """
    p = re.compile(
        '(/?([._:\w\d=~-]*/)*)(([a-zA-Z-]+)_[0-9]{1,3}C_[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9A-F]{4})\.(4\.0\.dict)')
    m = p.match(file_name)

    return (None, None) if m is None else (m.group(4), m.group(3))


def create_grammar_dir(dict_file_path, grammar_path, template_path, options) -> str:
    """
    Create grammar directory using specified .dict file and other files from template directory.

    :param dict_file_path: Path to .dict file.
    :param grammar_path: Path to a directory where newly created grammar should be stored.
    :param template_path: Path to template directory or language name installed with LG.
    :param options: Bit field that specifies multiple parsing options.
    :return: Path to newly created grammar directory.
    """

    if len(dict_file_path) == 0:
        raise LGParseError("Dictionary file name should not be empty.")

    if not os.path.isfile(dict_file_path):
        # The path is not specified correctly.
        if dict_file_path.find("/") >= 0:
            raise LGParseError("Dictionary path does not exist.")

        # If 'dict_file_path' is LG language short name such as 'en' then there must be a dictionary folder with the
        #   same name. If that's the case there is no need to create grammar folder, simply return the same name.
        #   Let LG handle it.
        elif os.path.isdir(LG_DICT_PATH + "/" + dict_file_path):
            return dict_file_path
        else:
            raise LGParseError("Dictionary path does not exist.")

    # Extract grammar name and a name of the new grammar directory from the file name
    (template_dict_name, dict_path) = get_dir_name(dict_file_path)

    if dict_path is None:
        raise LGParseError("Dictionary file name is expected to have proper notation.")

    dict_path = grammar_path + "/" + dict_path if dict_path is not None else dict_file_path

    # If template_dir is not specified
    if template_path is None:
        template_path = LG_DICT_PATH + "/" + template_dict_name

    # If template_dir is simply a language name such as 'en'
    elif template_path.find("/") == -1:
        template_path = LG_DICT_PATH + "/" + template_path

    # Raise exception if template_path does not exist
    if not os.path.isdir(template_path):
        raise FileNotFoundError("Directory '{0}' does not exist.".format(template_path))

    try:
        if os.path.isdir(dict_path):
            print("Info: Directory '" + dict_path + "' already exists.")

            if options & BIT_RM_DIR > 0:
                shutil.rmtree(dict_path, True)
                print("Info: Directory '" + dict_path + "' has been removed. Option '-r' was specified.")

        if not os.path.isdir(dict_path):
            # Create dictionary directory using existing one as a template
            shutil.copytree(template_path, dict_path)
            print("Info: Directory '" + dict_path + "' with template files has been created.")

            # Replace dictionary file '4.0.dict' with a new one
            shutil.copy(dict_file_path, dict_path + "/4.0.dict")
            print("Info: Dictionary file has been replaced with '" + dict_file_path + "'.")

    except IOError as err:
        print("IOError: " + str(err))
        return ""

    except FileNotFoundError as err:
        print("FileNotFoundError: " + str(err))
        return ""

    except OSError as err:
        print("OSError: " + str(err))
        return ""

    else:
        return dict_path


def create_dir(new_path) -> bool:
    """ Create directory specified by <new_path> """
    try:
        # If the subdirectory does not exist in destination root create it.
        if not os.path.isdir(new_path):
            print(new_path)
            os.mkdir(new_path)

    except OSError as err:
        print("Error: " + str(err))
        return False

    return True


def parse_corpus_files(src_dir, dst_dir, dict_dir, grammar_dir, template_dir, linkage_limit, options) -> int:
    """
    Traverse corpus folder parsing each file in that folder and subfolders. The function recreates source directory
        structure within the destination one and stores parsing results in newly created directory structure.
    :param src_dir: Source directory with corpus files.
    :param dst_dir: Destination directory to store parsing result files.
    :param dict_dir: Path to dictionary directory or file
    :param grammar_dir: Root directory path to store newly created grammar.
    :param template_dir: Path to template dictionary directory
    :param linkage_limit: Maximum number of linkages. Parammeter for LG API.
    :param options: Parse options bit field.
    :return:
    """
    def on_dict_file(path):
        """
        Callback function envoked for every .dict file specified.

        :param path: Path to .dict file
        :return:
        """
        file_count = 0
        full_ratio = 0.0
        none_ratio = 0.0            # probably should be 1.0
        avrg_ratio = 0.0

        new_grammar_path = ""
        new_dst_dir = dst_dir

        def recreate_struct(dir_path) -> bool:
            """
            Callback function that recreates directory structure of the source folder
            within the destination root directory.
            """
            return create_dir(new_dst_dir + "/" + dir_path[len(src_dir) + 1:])

        def on_corpus_file(file_path):

            ptr_parse = parse_file_with_lgp if (options & BIT_LG_EXE) else parse_file_with_api

            p, f = os.path.split(file_path)

            try:
                nonlocal file_count
                nonlocal full_ratio
                nonlocal none_ratio
                nonlocal avrg_ratio

                f_ratio, n_ratio, a_ratio = ptr_parse(new_grammar_path, file_path, os.path.join(new_dst_dir, f),
                                                    linkage_limit, options)

                file_count += 1
                full_ratio += f_ratio
                none_ratio += n_ratio
                avrg_ratio += a_ratio

            except OSError as err:
                print(str(err))


        # =============================================================================
        # def on_dict_file(path):
        # =============================================================================
        file_count = 0
        full_ratio = 0.0
        none_ratio = 0.0
        avrg_ratio = 0.0
        stat_path = None

        print("\nInfo: Testing grammar: '" + path + "'")

        new_grammar_path = create_grammar_dir(path, grammar_dir, template_dir, options)

        # Create subdirectory in dst_dir for newly created grammar
        gpath, gname = os.path.split(new_grammar_path)

        new_dst_dir = dst_dir

        # Create subdirectory in dst_dir for newly created grammar
        if not (options & BIT_DPATH_CREATE):
            new_dst_dir = dst_dir + "/" + gname

            if not create_dir(new_dst_dir):
                print("Error: Unable to create grammar subfolder: '{}'".format(gname))
                return
        else:
            end_pos = path.rfind("/")
            new_dst_dir = dst_dir + path[len(dict_dir):end_pos] if end_pos > 0 else path[len(dict_dir)-1:]

        # print("new_dst_dir='" + new_dst_dir + "'")

        # If src_dir is a directory then on_corpus_file() is invoked for every corpus file of the directory tree
        if os.path.isdir(src_dir):
            dpath, dname = os.path.split(src_dir)
            stat_path = new_dst_dir + "/" + dname + ".stat"
            traverse_dir(src_dir, "", on_corpus_file, recreate_struct, True)

        # If src_dir is a file then simply call on_corpus_file() for it
        elif os.path.isfile(src_dir):
            fpath, fname = os.path.split(src_dir)
            stat_path = new_dst_dir + "/" + fname + ".stat"
            on_corpus_file(src_dir)

        if file_count > 1:
            full_ratio /= float(file_count)
            none_ratio /= float(file_count)
            avrg_ratio /= float(file_count)

        stat_file_handle = None

        try:
            stat_file_handle = sys.stdout if stat_path is None else open(stat_path, "w")

            print("Total sentences parsed in full:\t{0[0]:2.2f}%\n"
                  "Total sentences not parsed at all:\t{0[1]:2.2f}%\nAverage sentence parse:\t{0[2]:2.2f}%\n".format(
                (full_ratio*100.0, none_ratio*100.0, avrg_ratio*100.0)), file=stat_file_handle)

        except IOError as err:
            print("IOError: " + str(err))

        except FileNotFoundError as err:
            print("FileNotFoundError: " + str(err))

        except OSError as err:
            print("OSError: " + str(err))

        finally:
            if stat_file_handle is not None and stat_file_handle != sys.stdout:
                stat_file_handle.close()


    def recreate_dict_struct(dir_path) -> bool:
        """
        Callback function that recreates directory structure of the source folder
        within the destination root directory.
        """
        return create_dir(dst_dir + "/" + dir_path[len(dict_dir) + 1:])

    # =============================================================================================================
    # def parse_corpus_files(src_dir, dst_dir, dict_dir, grammar_dir, template_dir, linkage_limit, options) -> int:
    # =============================================================================================================
    try:
        f_ptr = recreate_dict_struct if (options & BIT_DPATH_CREATE) == BIT_DPATH_CREATE else None

        # If dict_dir is the name of directory, hopefully with multiple .dict files to test
        #   then traverse the specified directory handling every .dict file in there.
        if os.path.isdir(dict_dir):
            traverse_dir(dict_dir, ".dict", on_dict_file, f_ptr, True)

        # Otherwise dic_dir might be either .dict file name, or LG shiped language name.
        else:
            on_dict_file(dict_dir)

    except LGParseError as err:
        print("LGParseError: " + str(err))
        return 1

    except Exception as err:
        print("Exception: " + str(err))
        return 2

    return 0


class PSSentence:
    def __init__(self, sent_text):
        self.text = sent_text
        self.linkages = []

def parse_batch_ps_output(text, lines_to_skip=3) -> []:
    """
    Parse postscript returned by link-parser executable in a form where each sentence is followed by zero
        or many postscript notated linkages. Postscript linkages are usually represented by three lines
        enclosed in brackets.
    :param text: String variable with postscript output returned by link-parser.
    :param lines_to_skip: Number of lines to skip before start parsing the text. It is necessary when additional
                parameters specified, when link-parser is invoked. In that case link-parser writes those parameter
                values on startup.
    """
    sentences = []

    line_count = 0      # line counter
    cur_sent = None     # current sentence
    cur_lnkg = ""       # current linkage

    # Parse output to get sentences and linkages in postscript notation
    for line in text.split("\n"):

        # Skip first 'lines_to_skip' lines and empty lines. Skip "Bye" line too.
        if line_count > lines_to_skip and len(line) and not line.startswith("Bye"):

            # If sentence line found, create line object and append it to the
            #   sentence list.
            if not line.startswith("["):
                cur_sent = PSSentence(line)
                sentences.append(cur_sent)

            # If postscript line found...
            else:
                # If that's the last line in postscript linkage sequence,
                #   complete the sequence and add linkage to the linkage list.
                if line == "[0]":
                    cur_lnkg += line
                    cur_sent.linkages.append(cur_lnkg)
                    cur_lnkg = ""

                # Otherwise add line to the linkage string
                else:
                    cur_lnkg += line

        # Increment line counter
        line_count += 1

    return sentences


def handle_stream_output(text, linkage_limit, options, out_stream):
    """
    Handle link-parser output stream text depending on options' BIT_OUTPUT field.

    :param text: Stream output text.
    :param linkage_limit: Number of linkages taken into account when statistics estimation is made.
    :param options: Integer variable with multiple bit fields
    :param out_stream: Output file stream handle.
    :return:
    """
    total_full_ratio, total_none_ratio, total_avrg_ratio = (0.0, 0.0, 0.0)

    # Parse only if 'ull' output format is specified.
    if not (options & BIT_OUTPUT):
        # Parse output into sentences and assotiate a list of linkages for each one of them.
        sentences = parse_batch_ps_output(text)

        sentence_count = 0

        # Parse linkages and make statistics estimation
        for sent in sentences:
            linkage_count = 0

            sent_full_ratio, sent_none_ratio, sent_avrg_ratio = (0.0, 0.0, 0.0)

            # Parse and calculate statistics for each linkage
            for lnkg in sent.linkages:
                if linkage_count == linkage_limit:
                    break

                f, n, a = parse_postscript(lnkg, options, out_stream)

                sent_full_ratio += f
                sent_none_ratio += n
                sent_avrg_ratio += a

                linkage_count += 1

            if linkage_count > 1:
                sent_full_ratio /= float(linkage_count)
                sent_none_ratio /= float(linkage_count)
                sent_avrg_ratio /= float(linkage_count)

            total_full_ratio += sent_avrg_ratio
            total_none_ratio += sent_none_ratio
            total_avrg_ratio += sent_avrg_ratio

            sentence_count += 1

        if sentence_count > 1:
            total_full_ratio /= float(sentence_count)
            total_none_ratio /= float(sentence_count)
            total_avrg_ratio /= float(sentence_count)

    # If output format is other than ull then simply write text to the output stream.
    else:
        print(text, file=out_stream)

    return (total_full_ratio, total_none_ratio, total_avrg_ratio)


def parse_file_with_lgp(dict_path, corpus_path, output_path, linkage_limit, options) \
        -> (float, float, float):
    """
    Link parser invocation routine. Runs link-parser executable in a separate process.

    :param dict_path: name or path to the dictionary
    :param corpus_path: path to the test text file
    :param output_path: output file path
    :param linkage_limit: maximum number of linkages LG may return when parsing a sentence
    :param options: bit field. Use bit mask constants to set or reset one or multiple bits:
                BIT_CAPS  = 0x01    Keep capitalized letters in tokens untouched if set,
                                    make all lowercase otherwise.
                BIT_RWALL = 0x02    Keep all links with RIGHT-WALL if set, ignore them otherwise.
                BIT_STRIP = 0x04    Strip off token suffixes if set, remove them otherwise.
    :return: tuple (float, float, float):
                - percentage of totally parsed sentences;
                - percentage of completely unparsed sentences;
                - percentage of parsed sentences;
    """

    print("Info: Parsing a corpus file: '" + corpus_path + "'")
    print("Info: Using dictionary: '" + dict_path + "'")

    if output_path is not None:
        print("Info: Parses are saved in: '" + output_path+get_output_suffix(options) + "'")
    else:
        print("Info: Output file name is not specified. Parses are redirected to 'stdout'.")

    # Statistics return value initialization
    ret_tup = (0.0, 0.0, 0.0)

    reg_exp = "^\D.+$" if (options & BIT_ULL_IN) == BIT_ULL_IN else "^[^#].+$"

    # Make command option list depending on the output format specified.
    if not (options & BIT_OUTPUT) or (options & BIT_OUTPUT_POSTSCRIPT):
        cmd = ["link-parser", dict_path, "-echo=1", "-postscript=1", "-graphics=0", "-verbosity=0"]
    elif (options & BIT_OUTPUT_CONST_TREE):
        cmd = ["link-parser", dict_path, "-echo=1", "-constituents=1", "-graphics=0", "-verbosity=0"]
    else:
        cmd = ["link-parser", dict_path, "-echo=1", "-graphics=1", "-verbosity=0"]

    out_stream = None

    try:
        out_stream = sys.stdout if output_path is None else open(output_path+get_output_suffix(options), "w")

        with Popen(["grep", "-P", reg_exp, corpus_path], stdout=PIPE) as proc_grep, \
             Popen(cmd, stdin=proc_grep.stdout, stdout=PIPE) as proc_pars:

            # Closing grep output stream will terminate it's process.
            proc_grep.stdout.close()

            # Read pipe to get complete output returned by link-parser
            text = proc_pars.communicate()[0].decode()

            # Take an action depending on the output format specified by 'options'
            ret_tup = handle_stream_output(text, linkage_limit, options, out_stream)

    except IOError as err:
        print(str(err))

    except FileNotFoundError as err:
        print(str(err))

    except OSError as err:
        print("OSError: " + str(err))

    except Exception as err:
        print("Exception: " + str(err))

    finally:
        if out_stream is not None and out_stream != sys.stdout:
            out_stream.close()

        return ret_tup
