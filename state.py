import types
import collections

# manage a stack of states to implement undo/redo functionality
#  on a collection of objects implementing the Observable mixin
class UndoStack(object):
  def __init__(self):
    self.actions = [ ]
    self.position = 0
  
  # store the state of the given objects before changes are made
  def begin_action(self, things):
    self._begin_state = self.save_state(things)
  # store the state of the given objects after changes are made
  def end_action(self, things):
    # see what changed in the course of the action
    begin_state = self._begin_state
    end_state = self.save_state(things)
    keys = end_state.keys()
    for key in keys:
      if ((key in begin_state) and 
          (begin_state[key] == end_state[key])):
        del begin_state[key]
        del end_state[key]
    # clear the stored beginning state
    self._begin_state = None
    # if no changes were made, don't record an action
    if ((len(begin_state) == 0) and (len(end_state) == 0)): return
    # remove all actions past the current position
    self.actions = self.actions[0:self.position]
    # add a reversible action to the stack
    self.actions.append((begin_state, end_state))
    self.position += 1
  
  # return whether it's possible to undo/redo
  @property
  def can_undo(self):
    return((self.position is not None) and 
           (self.position > 0))
  @property
  def can_redo(self):
    return((self.position is not None) and 
           (self.position < len(self.actions)))
           
  # undo the last action
  def undo(self):
    if (not self.can_undo): return
    self.position -= 1
    self.restore_state(self.actions[self.position][0])
    
  # redo the last undone action
  def redo(self):
    if (not self.can_redo): return
    self.restore_state(self.actions[self.position][1])
    self.position += 1
    
  # walk all attributes and members of the given items and store them
  #  to a single dictionary
  def save_state(self, thing, state=None):
    if (state is None):
      state = collections.OrderedDict()
    # don't store the state of tuples, since they're immutable and can't
    #  be restored
    if (type(thing) is types.TupleType):
      for item in thing:
        self.save_state(item, state)
      return(state)  
    # determine whether we can store the thing's state in the dict
    hashable = hasattr(thing, '__hash__')
    # if the item is a sequence, save state of all items in it
    try:
      for item in thing:
        self.save_state(item, state)
      # if the sequence can itself be hashed, store its items as a plain list
      if (hashable):
        state[(thing, '_list')] = tuple(thing)
    except TypeError: pass
    # store the thing's attributes
    if (hashable):
      for key in dir(thing):
        # skip private stuff
        if (key[0] == '_'): continue
        value = getattr(thing, key)
        # skip methods
        if (callable(value)): continue
        # all observable objects should have their state stored
        if (hasattr(value, 'on_change')):
          self.save_state(value, state)
        # all views should have their models stored
        if (hasattr(value, 'model')):
          self.save_state(value.model, state)
        # only store the values of settable properties
        try:
          if (type(thing).__dict__[key].fset is not None):
            # copy lists and dictionaries so we're not storing a reference
            #  to a mutable value
            if (type(value) is types.DictType):
              value = dict(value)
            elif (type(value) is types.ListType):
              value = tuple(value)
            state[(thing, key)] = value
        except KeyError: pass
        except AttributeError: pass
    return(state)
  # restore state from a dictionary generated by calling save_state
  def restore_state(self, state):
    for (ref, value) in state.iteritems():
      (thing, key) = ref
      if (key == '_list'):
        thing[0:] = value
      else:
        setattr(thing, key, value)

