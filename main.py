import math

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.resources import resource_find
from kivy.uix.button import Button
from kivy.graphics.transformation import Matrix
from kivy.uix.floatlayout import FloatLayout
from kivy.graphics.opengl import *
from kivy.graphics.gl_instructions import ClearBuffers
from kivy.graphics import *
from objloader import ObjFileLoader
from kivy.logger import Logger
from rotation import SingleRotate
from kivy.uix.widget import Widget
from kivy.graphics.fbo import Fbo
from kivy.properties import ObjectProperty

class Renderer(Widget):
    
    texture = ObjectProperty(None, allownone=True)    
    
    def __init__(self, **kwargs):

        #self.canvas = RenderContext(compute_normal_mat=True)
        #self.canvas.shader.source = resource_find('simple.glsl')
        self.canvas = Canvas()
        self.scene = ObjFileLoader(resource_find("testnurbs.obj"))
        
        self.meshes = []
        
        with self.canvas:
            self.fbo = Fbo(size=self.size, with_depthbuffer=True, compute_normal_mat=True, clear_color=(0., 0., 0., 0.))
            self.viewport = Rectangle(size=self.size, pos=self.pos)
        self.fbo.shader.source = resource_find('simple.glsl')
        #self.texture = self.fbo.texture
        

        super(Renderer, self).__init__(**kwargs)

        with self.fbo:
            #ClearBuffers(clear_depth=True)
            
            self.cb = Callback(self.setup_gl_context)
            PushMatrix()
            self.setup_scene()
            PopMatrix()
            self.cb = Callback(self.reset_gl_context)

        
        Clock.schedule_interval(self.update_scene, 1 / 60.)
        
        self._touches = []

    def on_size(self, instance, value):
        self.fbo.size = value
        self.viewport.texture = self.fbo.texture
        self.viewport.size = value
        self.update_glsl()

    def on_pos(self, instance, value):
        self.viewport.pos = value

    def on_texture(self, instance, value):
        self.viewport.texture = value


    def setup_gl_context(self, *args):
        #clear_buffer
        glEnable(GL_DEPTH_TEST)
        self.fbo.clear_buffer()
        #glDepthMask(GL_FALSE);

    def reset_gl_context(self, *args):
        glDisable(GL_DEPTH_TEST)
        

    def update_glsl(self, *largs):
        asp = self.width / float(self.height)
        proj = Matrix().view_clip(-asp, asp, -1, 1, 1, 100, 1)
        self.fbo['projection_mat'] = proj

    def setup_scene(self):
        Color(1, 1, 1, 0)

        PushMatrix()
        Translate(0, 0, -5)
        # This Kivy native Rotation is used just for
        # enabling rotation scene like trackball
        self.rotx = Rotate(0, 1, 0, 0)
        self.roty = Rotate(-120, 0, 1, 0) # here just rotate scene for best view
        self.scale = Scale(1)
                
        UpdateNormalMatrix()
        
        self.draw_elements()
        
        PopMatrix()

    def draw_elements(self):
        """ Draw separately all objects on the scene
            to setup separate rotation for each object
        """
        def _draw_element(m):
            Mesh(
                vertices=m.vertices,
                indices=m.indices,
                fmt=m.vertex_format,
                mode='triangles',
            )
            
        def _set_color(*color, **kw):
            id_color = kw.pop('id_color', (0, 0, 0))
            return ChangeState(
                        Kd=color,
                        Ka=color,
                        Ks=(.3, .3, .3),
                        Tr=1., Ns=1.,
                        intensity=1.,
                        id_color=[i / 255. for i in id_color],
                    )
            
        # Draw sphere in the center
        sphere = self.scene.objects['Sphere']
        _set_color(0.7, 0.7, 0., id_color=(255, 255, 0))
        _draw_element(sphere)
        
        # Then draw other elements and totate it in different axis
        pyramid = self.scene.objects['Pyramid']
        PushMatrix()
        self.pyramid_rot = Rotate(0, 0, 0, 1)
        _set_color(0., 0., .7, id_color=(0., 0., 255))
        _draw_element(pyramid)
        PopMatrix()
        
        box = self.scene.objects['Box']
        PushMatrix()
        self.box_rot = Rotate(0, 0, 1, 0)
        _set_color(.7, 0., 0., id_color=(255, 0., 0))
        _draw_element(box)
        PopMatrix()

        cylinder = self.scene.objects['Cylinder']
        PushMatrix()
        self.cylinder_rot = Rotate(0, 1, 0, 0)
        _set_color(0.0, .7, 0., id_color=(0., 255, 0))
        _draw_element(cylinder)
        PopMatrix()
    

    def update_scene(self, *largs):
        self.pyramid_rot.angle += 0.5
        self.box_rot.angle += 0.5
        self.cylinder_rot.angle += 0.5
        
    
    # =============== All stuff after is for trackball implementation =============
        
    def define_rotate_angle(self, touch):
        x_angle = (touch.dx/self.width)*360
        y_angle = -1*(touch.dy/self.height)*360
        return x_angle, y_angle
    
    def on_touch_down(self, touch):
        self._touch = touch
        touch.grab(self)
        self._touches.append(touch)
        
    def on_touch_up(self, touch): 
        touch.ungrab(self)
        self._touches.remove(touch)
        self.fbo.shader.source = 'select_mode.glsl'
        self.fbo.ask_update()
        self.fbo.draw()
        print self.fbo.get_pixel_color(touch.x, touch.y)
        self.fbo.shader.source = 'simple.glsl'
        self.fbo.ask_update()
        self.fbo.draw()
    
    def on_touch_move(self, touch): 

        self.update_glsl()
        if touch in self._touches and touch.grab_current == self:
            if len(self._touches) == 1:
                # here do just rotation        
                ax, ay = self.define_rotate_angle(touch)
                
                self.roty.angle += ax
                self.rotx.angle += ay

            elif len(self._touches) == 2: # scaling here
                #use two touches to determine do we need scal
                touch1, touch2 = self._touches 
                old_pos1 = (touch1.x - touch1.dx, touch1.y - touch1.dy)
                old_pos2 = (touch2.x - touch2.dx, touch2.y - touch2.dy)
                
                old_dx = old_pos1[0] - old_pos2[0]
                old_dy = old_pos1[1] - old_pos2[1]
                
                old_distance = (old_dx*old_dx + old_dy*old_dy)
                Logger.debug('Old distance: %s' % old_distance)
                
                new_dx = touch1.x - touch2.x
                new_dy = touch1.y - touch2.y
                
                new_distance = (new_dx*new_dx + new_dy*new_dy)
                
                Logger.debug('New distance: %s' % new_distance)
                SCALE_FACTOR = 0.01
                
                if new_distance > old_distance: 
                    scale = SCALE_FACTOR
                    Logger.debug('Scale up')
                elif new_distance == old_distance:
                    scale = 0
                else:
                    scale = -1*SCALE_FACTOR
                    Logger.debug('Scale down')
                    
                xyz = self.scale.xyz
                
                if scale:
                    self.scale.xyz = tuple(p + scale for p in xyz)
        

class RendererApp(App):
    def build(self):
        root = FloatLayout()
        renderer = Renderer()
        btn = Button(size_hint=(None, None), size=root.size, text="Hello world", pos=(0, 0), font_size="120dp")
        root.add_widget(btn)
        root.add_widget(renderer)
        #root.add_widget(btn)
        def _on_resize(inst, value):
            btn.size = value
        root.bind(size=_on_resize)
        return root
        
        
if __name__ == "__main__":
    RendererApp().run()
