# Presidential Rectangle

The Presidential Rectangle puzzle asks for a packing of all U.S. presidential surnames into the smallest possible rectangle subject to the following conditions:

   * Names can only be placed left-to-right or top-to-bottom
   * Letters in adjacent cells must belong to a common name
   * Every name must be connected by some path of intersecting names to every other name

You can read more background about the puzzle and these tools in [this post](https://blog.aaw.io/2021/11/07/the-presidential-rectangle.html).

Here's a 21-by-21 solution for the current set of 40 presidential surnames, as of 2021:

![](21-by-21.png)

## Setup

You'll need a SAT solver that accepts DIMACS CNF files as input. I'll use [kissat](https://github.com/arminbiere/kissat.git) in
examples below. You'll also need python3 intalled.

## Examples

The workflow is basically:

   1. Generate a DIMACS CNF file with appropriate constraints
   2. Find a solution or prove one doesn't exist with a SAT solver
   3. Extract a solution if one exists, otherwise try again

The Presidential Rectangle seems to difficult to solve directly, so these tools allow you to specify many more types of contstraints to zero in
on specific solutions. First, to illustrate the workflow, here's how you'd find the smallest rectangle containing the words ZERO, ONE, ..., TEN:

```
# Generate constraints for an 8-by-8 rectangle containing words from data/numbers-10:
$ generate-sat.py data/numbers-10 8 8 > /tmp/numbers.cnf

# Run a SAT solver on the input, store the output. 
# (This might take a minute, tail the output for progress.)
$ kissat /tmp/numbers.cnf > /tmp/numbers.out

# Was the solver successful? Exit code is 10 for success, 20 for failure:
$ echo $?
10

# Since the solver was successful, you can extract the discovered 8-by-8 solution:
$ decode-solution.py /tmp/numbers.cnf /tmp/numbers.out 8 8
  FIVE  
TWO  I  
  U  G  
ZERO H  
   N TEN
SEVEN  I
I      N
X  THREE

# You can also prove that such a packing is impossible in a 7-by-7 rectangle:
$ generate-sat.py data/numbers-10 8 8 > /tmp/numbers.cnf
$ kissat /tmp/numbers.cnf > /tmp/numbers.out
$ echo $?
20
```
