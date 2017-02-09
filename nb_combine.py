"""
This script is designed to support active reading.  It takes as input
a set of ipython notebook as well as some target cells which define a set
of reading exercises.  The script processes the collection of notebooks
and builds a notebook which summarizes the responses to each question.

Original work by Paul Ruvolo.
Adapted by Oliver Steele
"""

# TODO backport to olin-computing/classroom-tools, and include via submodule or package
# TODO adding and parsing the cell metadata is messy. It dates from when the nb author supplied this

import re
from collections import OrderedDict
from copy import deepcopy

import Levenshtein
import nbformat
from cached_property import cached_property
from numpy import argmin

# Constants
#

QUESTION_RE = r'#+ Exercise'
POLL_RE = r'#+ .*(poll|Notes for the Instructors|Reading Journal Feedback)'
CLEAR_OUTPUTS = True


# Functions
#

def nb_add_metadata(nb, owner=None):
    if owner:
        nb['metadata']['owner'] = owner
    for cell in nb['cells']:
        if cell['cell_type'] == 'markdown' and cell['source']:
            if re.match(QUESTION_RE, cell['source'], re.IGNORECASE):
                cell['metadata']['is_question'] = True
            elif re.match(POLL_RE, cell['source'], re.IGNORECASE):
                cell['metadata']['is_question'] = True
                cell['metadata']['is_poll'] = True
    return nb


def safe_read_notebook(string, owner=None, clear_outputs=False):
    try:
        nb = nbformat.reads(string, as_version=4)
    except nbformat.reader.NotJSONError:
        return None
    nb = nb_add_metadata(nb, owner)
    if clear_outputs:
        for cell in nb['cells']:
            if 'outputs' in cell:
                cell['outputs'] = []
    return nb


def nb_combine(template_notebook, student_notebooks):
    nbe = NotebookExtractor(template_notebook, student_notebooks)
    return nbe.get_combined_notebook()


# The extractor
#

class NotebookExtractor(object):
    """The top-level class for extracting answers from a notebook.

    TODO: add support multiple notebooks
    """

    MATCH_THRESH = 10  # maximum edit distance to consider something a match

    def __init__(self, notebook_template, notebooks):
        """Initialize with the specified notebook URLs and list of question prompts."""
        self.template = nb_add_metadata(notebook_template)
        self.notebooks = notebooks.values()
        self.usernames = notebooks.keys()
        self._processed = False

    @cached_property
    def question_prompts(self):
        """Return a list of `QuestionPrompt`.

        Each cell with metadata `is_question` truthy produces an instance of `QuestionPrompt`.
        """
        prompts = []
        prev_prompt = None
        for idx, cell in enumerate(self.template['cells']):
            is_final_cell = idx + 1 == len(self.template['cells'])
            metadata = cell['metadata']
            if metadata.get('is_question', False):
                cell_source = cell['source']
                if prev_prompt is not None:
                    prompts[-1].stop_md = cell_source
                is_poll = metadata.get('is_poll', 'Reading Journal feedback' in cell_source.split('\n')[0])
                prompts.append(QuestionPrompt(question_heading='',
                                              name=metadata.get('problem', None),
                                              index=len(prompts),
                                              start_md=cell_source,
                                              stop_md='next_cell',
                                              is_optional=metadata.get('is_optional', None),
                                              is_poll=is_poll
                                              ))
                if metadata.get('allow_multi_cell', False):
                    prev_prompt = prompts[-1]
                    # if it's the last cell, take everything else
                    if is_final_cell:
                        prompts[-1].stop_md = ''
                else:
                    prev_prompt = None
        return prompts

    def _process(self):
        """Filter the notebook at the notebook_URL so that it only contains the questions and answers to the reading."""
        nbs = dict(zip(self.usernames, self.notebooks))

        for prompt in self.question_prompts:
            prompt.answer_status = {}
            for gh_username, notebook_content in nbs.items():
                if notebook_content is None:
                    continue
                suppress_non_answer = bool(prompt.answers)
                response_cells = \
                    prompt.get_closest_match(notebook_content['cells'],
                                             NotebookExtractor.MATCH_THRESH,
                                             suppress_non_answer)
                if not response_cells:
                    status = 'missed'
                elif not response_cells[-1]['source'] or not NotebookUtils.cell_list_text(response_cells):
                    status = 'blank'
                else:
                    status = 'answered'
                    if not suppress_non_answer:
                        # If it's the first notebook with this answer, extract the questions from it.
                        # This is kind of a bass-ackwards way to do this; it's incremental from the previous
                        # strategy.
                        prompt.cells = [cell for cell in response_cells
                                        if cell['metadata'].get('is_question', False)]
                        response_cells = [cell for cell in response_cells if cell not in prompt.cells]
                    prompt.answers[gh_username] = response_cells
                prompt.answer_status[gh_username] = status

        self._processed = True

        # FIXME doesn't work because questions are collected into first response
        # sort_responses = not self.include_usernames
        # if sort_responses:
        #     def cell_slines_length(response_cells):
        #         return len('\n'.join(cell['source') for cell in response_cells).strip())
        #     for prompt in self.question_prompts:
        #         prompt.answers = OrderedDict(sorted(prompt.answers.items(), key=lambda t: cell_slines_length(t[1])))

    def get_combined_notebook(self, include_usernames=False):
        if not self._processed:
            self._process()

        remove_duplicate_answers = not include_usernames
        filtered_cells = []
        for prompt in self.question_prompts:
            filtered_cells += prompt.cells
            answers = prompt.answers_without_duplicates if remove_duplicate_answers else prompt.answers
            for gh_username, response_cells in answers.items():
                if include_usernames:
                    filtered_cells.append(
                        NotebookUtils.markdown_heading_cell(self.gh_username_to_fullname(gh_username), 4))
                filtered_cells.extend(response_cells)

        answer_book = deepcopy(self.template)
        answer_book['cells'] = filtered_cells
        return answer_book

    def report_missing_answers(self):
        if not self._processed:
            self._process()

        return [(prompt.name, prompt.answer_status) for prompt in self.question_prompts
                if not prompt.is_poll and not prompt.is_optional]


class QuestionPrompt(object):
    def __init__(self, question_heading, start_md, stop_md, name=None, index=None, is_poll=False, is_optional=None):
        """Initialize a question prompt.

        Initialize a question prompt with the specified starting markdown (the question), and stopping
        markdown (the markdown from the next content cell in the notebook).  To read to the end of the
        notebook, set stop_md to the empty string.  The heading to use in the summary notebook before
        the extracted responses is contined in question_heading.
        To omit the question heading, specify the empty string.
        """
        if is_optional is None and start_md:
            is_optional = bool(re.search(r'optional', start_md.split('\n')[0], re.I))
        self.question_heading = question_heading
        self._name = name
        self.start_md = start_md
        self.stop_md = stop_md
        self.is_optional = is_optional
        self.is_poll = is_poll
        self.index = index
        self.answers = OrderedDict()
        self.cells = []

    @property
    def answers_without_duplicates(self):
        answers = dict(self.answers)
        answer_strings = set()  # answers to this question, as strings; used to avoid duplicates
        for username, response_cells in self.answers.items():
            answer_string = '\n'.join(cell['source'] for cell in response_cells).strip()
            if answer_string in answer_strings:
                del answers[username]
            else:
                answer_strings.add(answer_string)
        return answers

    @property
    def name(self):
        m = re.match(r'^#+\s*(.+)\n', self.start_md)
        if self._name:
            return self._name
        format_str = {
            (False, False): '',
            (False, True): '{title}',
            (True, False): '{number}',
            (True, True): '{number}. {title}'
        }[isinstance(self.index, int), bool(m)]
        return format_str.format(number=(self.index or 0) + 1, title=m and m.group(1))

    def get_closest_match(self,
                          cells,
                          matching_threshold,
                          suppress_non_answer_cells=False):
        """Return a list of cells that most closely match the question prompt.

        If no match is better than the matching_threshold, the empty list will be returned.
        """
        return_value = []
        distances = [Levenshtein.distance(self.start_md, cell['source'])
                     for cell in cells]
        if min(distances) > matching_threshold:
            return return_value

        best_match = argmin(distances)
        if self.stop_md == u"next_cell":
            end_offset = 2
        elif len(self.stop_md) == 0:
            end_offset = len(cells) - best_match
        else:
            distances = [Levenshtein.distance(self.stop_md, cell['source'])
                         for cell in cells[best_match:]]
            if min(distances) > matching_threshold:
                return return_value
            end_offset = argmin(distances)
        if len(self.question_heading) != 0 and not suppress_non_answer_cells:
            return_value.append(NotebookUtils.markdown_heading_cell(self.question_heading, 2))
        if not suppress_non_answer_cells:
            return_value.append(cells[best_match])
        return_value.extend(cells[best_match + 1:best_match + end_offset])
        return return_value


class NotebookUtils(object):
    @staticmethod
    def markdown_heading_cell(text, heading_level):
        """Create a Markdown cell with the specified text at the specified heading_level.

        E.g. mark_down_heading_cell('Notebook Title','#')
        """
        return {
            'cell_type': 'markdown',
            'metadata': {},
            'source': '#' * heading_level + ' ' + text
        }

    @staticmethod
    def cell_list_text(cells):
        return ''.join(cell['source'] for cell in cells).strip()
