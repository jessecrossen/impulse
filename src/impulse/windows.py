import os, sys

from gi.repository import Gtk, Gdk, Gio

from models import doc, controllers
import views.track
import views.doc
from views.core import ViewManager
from midi import inputs, sampler

class DocumentWindow(Gtk.ApplicationWindow):
  def __init__(self, app):
    Gtk.ApplicationWindow.__init__(self, application=app,
                                         title="Impulse")
    self._document = None
    # bind to the application
    self.app = app
    # set default size
    self.set_default_size(800, 600)
    # make a toolbar
    self._make_actions()
    self._make_toolbar()
    # make some widgets for the main content
    self.box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
    self.add(self.box)
    self.box.pack_start(self.toolbar, False, False, 0)
    # initialize state
    self.control_surface = None
    self.transport = None
    self.mixer = None
    self.recorder = None
    self.player = None
    # start with an empty document
    self.document_view = None
    self.document = doc.Document()
    
  @property
  def document(self):
    return(self._document)
  @document.setter
  def document(self, value):
    # detach from the old document
    if (self._document is not None):
      self.detach()
      self._document = None
    # attach to the new document
    if (value is not None):
      self._document = value
      self.attach()
  # detach from the current document
  def detach(self):
    self._unbind_actions()
    # detach from the old document
    self.transport = None
    self.mixer = None
    self.recorder = None
    self.player = None
    if (self.control_surface):
      self.control_surface.disconnect()
    self.control_surface = None
    # kill the document view
    if (self.document_view is not None):
      self.document_view.destroy()
      self.document_view = None
    # dump the undo stack and clear the selection
    ViewManager.reset()
  # attach to a new document
  def attach(self):
    # make a mixer and transport
    self.mixer = controllers.Mixer(self.document.tracks)
    self.transport = controllers.Transport()
    self.control_surface = inputs.NanoKONTROL2(
      transport=self.transport, mixer=self.mixer)
    # add record/playback controllers
    self.recorder = controllers.Recorder(
      transport=self.transport,
      input_patch_bay=self._document.input_patch_bay,
      output_patch_bay=self._document.output_patch_bay)
    self.player = controllers.Player(
      transport=self.transport,
      output_patch_bay=self._document.output_patch_bay)
    # make a view for the document
    self.document_view = views.doc.DocumentView(
      document=self._document,
      transport=self.transport)
    self.box.pack_end(self.document_view, True, True, 0)
    # bind actions for the new document
    self._bind_actions()
    # show the document view
    self.show_all()
  
  # make actions on the document
  def _make_actions(self):
    # undo/redo actions
    self.undo_action = self.make_action('undo', '<Control>z')
    self.redo_action = self.make_action('redo', '<Control><Shift>z')
    # transport actions
    self.back_action = self.make_action('transportBack')
    self.forward_action = self.make_action('transportForward')
    self.stop_action = self.make_action('transportStop')
    self.play_action = self.make_action('transportPlay')
    self.record_action = self.make_action('transportRecord')
    # track/output actions
    self.add_track_action = self.make_action('addTrack', '<Control>t')
    self.add_output_action = self.make_action('addOutput', '<Control>o')
    # zoom actions
    self.zoom_in_action = self.make_action('zoomIn', 
      '<Control><Shift>plus')
    self.zoom_out_action = self.make_action('zoomOut', 
      '<Control><Shift>underscore')
    # keep a list of action bindings so we can unbind them later
    self._action_bindings = [ ]
  # make an action with an optional accelerator
  def make_action(self, name, accel=None):
    action = Gio.SimpleAction.new(name, None)
    if (accel):
      self.app.add_accelerator(accel, 'win.'+name, None)
    self.add_action(action)
    return(action)
  # bind document actions
  def _bind_actions(self):
    # undo/redo
    self._bind_action(self.undo_action, ViewManager.undo)
    self._bind_action(self.redo_action, ViewManager.redo)
    # transport
    t = self.transport
    self._bind_action(self.back_action, t.skip_back)
    self._bind_action(self.forward_action, t.skip_forward)
    self._bind_action(self.stop_action, t.stop)
    self._bind_action(self.play_action, t.play)
    self._bind_action(self.record_action, t.record)
    # zoom
    self._bind_action(self.zoom_in_action, self.document_view.zoom_in)
    self._bind_action(self.zoom_out_action, self.document_view.zoom_out)
    # track/output
    self._bind_action(self.add_track_action, self.document.add_track)
    self._bind_action(self.add_output_action, self.document_view.add_output)
    # update action state
    self.document_view.time_scale.add_observer(self.update_actions)
    self.document.tracks.add_observer(self.update_actions)
    ViewManager.add_observer(self.update_actions)
    sampler.LinuxSampler.add_observer(self.update_actions)
    self.update_actions()
  # unbind all actions
  def _unbind_actions(self):
    for (action, handler) in self._action_bindings:
      action.disconnect(handler)
    ViewManager.remove_observer(self.update_actions)
    sampler.LinuxSampler.remove_observer(self.update_actions)
    self.document.tracks.remove_observer(self.update_actions)
    self.document_view.time_scale.remove_observer(self.update_actions)
  # bind to an action and remember the binding
  def _bind_action(self, action, callback):
    handler = action.connect('activate', callback)
    self._action_bindings.append((action, handler))
  # reflect changes to models in the action buttons
  def update_actions(self):
    self.undo_action.set_enabled(ViewManager.can_undo)
    self.redo_action.set_enabled(ViewManager.can_redo)
    self.zoom_in_action.set_enabled(self.document_view.can_zoom_in)
    self.zoom_out_action.set_enabled(self.document_view.can_zoom_out)
    # only allow recording if a track is armed
    track_armed = False
    for track in self.document.tracks:
      if (track.arm):
        track_armed = True
        break
    self.record_action.set_enabled(track_armed)
    # only allow adding instruments if the sampler is ready
    self.add_output_action.set_enabled(
      (sampler.LinuxSampler.ready) and 
      (sampler.LinuxSampler.input_connected) and 
      (sampler.LinuxSampler.output_connected))
  # make a toolbar with document actions
  def _make_toolbar(self):
    # make a toolbar
    t = Gtk.Toolbar.new()
    self.toolbar = t
    # transport actions
    t.add(Gtk.ToolButton(Gtk.STOCK_MEDIA_REWIND, 
                         action_name='win.transportBack'))
    t.add(Gtk.ToolButton(Gtk.STOCK_MEDIA_FORWARD, 
                         action_name='win.transportForward'))
    t.add(Gtk.ToolButton(Gtk.STOCK_MEDIA_STOP, 
                         action_name='win.transportStop'))
    t.add(Gtk.ToolButton(Gtk.STOCK_MEDIA_PLAY, 
                         action_name='win.transportPlay'))
    t.add(Gtk.ToolButton(Gtk.STOCK_MEDIA_RECORD, 
                         action_name='win.transportRecord'))
    t.add(Gtk.SeparatorToolItem())
    # undo/redo
    t.add(Gtk.ToolButton(Gtk.STOCK_UNDO, action_name='win.undo'))
    t.add(Gtk.ToolButton(Gtk.STOCK_REDO, action_name='win.redo'))
    t.add(Gtk.SeparatorToolItem())
    # zoom
    t.add(Gtk.ToolButton(Gtk.STOCK_ZOOM_OUT, action_name='win.zoomOut'))
    t.add(Gtk.ToolButton(Gtk.STOCK_ZOOM_IN, action_name='win.zoomIn'))
    
