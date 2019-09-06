import ipywidgets as w
from ipywidgets import Layout, Box
import bqplot as bq
import numpy as np

#debugging output to widget                                 
out = w.Output(layout={'border': '1px solid black'})
    
    
class Lightcurve_plot():
    '''plot utility for lightcurves'''
    
    
    def __init__(self, filters = ['G', 'R', 'I'], filter_button_colors = ['green','red','magenta']):
        '''Initialize plot widget'''

        #define filters
        self.filters = filters
        self.filter_button_colors = filter_button_colors
        self.n_filters = len(self.filters)

        #initialize data
        self.x = []
        self.data = []
        self.err = []
        self.diffImage = []
        self.tempImage = []
        self.sciImage = []

        #define scales for axes 
        self.sc_x = bq.LinearScale()
        self.sc_y = bq.LinearScale(reverse=True)
       
        #initial widgets
        self.filter_togglebuttons()
        self.initialize_widget()
        
        
        #plot initial widget
        self.plot()
        
    def set_title (self, name):
        '''Set object name'''

        #Set Label background color https://github.com/jupyter-widgets/ipywidgets/issues/577                                                                      
        if (hasattr(self, 'title') == False):
            data_input_style = "<style>.data_input  { background-color:#a3a6b8 !important; }</style>"
            self.title = w.Label(value=' ObjectId: {}'.format(name),)
            self.title.add_class('data_input')
            
            self.title_items = [
            w.HTML(data_input_style),
            self.title
            ]
        else:
            self.title.value = ' ObjectId: {}'.format(name)

    def filter_togglebuttons(self):
        '''Widget to display filters'''

        #define number of filters and adjust layout
        #+1 to account for fold radio button
        filter_button_size = 100./(self.n_filters + 1)
        filter_button_layout = Layout(width='{}%'.format(filter_button_size))

        self.filter_items = [w.ToggleButton(value=False, description=item, disabled=False,
                              tooltip='Plot lightcurve for {} filter'.format(item),
                              layout=filter_button_layout,
                              style = w.ToggleButtonsStyle(button_color=color),
                              selected={'opacity': 0.5},
                                        )
                             for item,color in zip(self.filters, self.filter_button_colors)]

        #setup button interactions                                                                                                     
        for item in self.filter_items:
            item.observe(self.filter_change, 'value')

    def fold_radiobutton(self):
        '''Create fold it radio button'''
        self.fold_button = w.RadioButtons(
            options=['fold'],
            #     value='pineapple',
            description='Fold lightcurve',
            disabled=False
        )
        self.fold_radiobutton.observe(self.set_fold, 'value')

    def set_fold(self, change):
        '''Set fold lightcurve parameter'''
        if (change.new == True):
            self.fold = True
        else:
            self.fold = False

    def get_selected_filters(self, filter_marks):
        '''return the list of selected filters'''
        return [item.description for item in filter_marks if item.value==True]

    def plot_scatter(self, x=[], y=[], color='red', filt=''):
        '''Create and return Scatter plot'''
        #TODO: tooltip format with all data                                                                                        
        tooltip = bq.Tooltip(fields=['x', 'y'], formats=['.2f', '.2f'])
        scatt = bq.Scatter(
                default_size=3,
                scales={'x': self.sc_x, 'y': self.sc_y},
                tooltip=tooltip,
                tooltip_style={'opacity': 0.5},
                interactions={'hover': 'tooltip'},
                unhovered_style={'opacity': 0.5},
                display_legend=True)
        scatt.colors = [color]
        scatt.label = filt
        if ((y != [])):
            scatt.x = x
            scatt.y = y
        scatt.on_element_click(self.plot_images)
        
        return scatt

    def plot_errorbar(self, x=[], y=[], err_y = [],  color='red'):
        '''Create and return errorbars using OHLC format'''
        vals = [[yval-dy,yval+dy,yval-dy,yval+dy] for yval,dy in zip(y,err_y)]
        #print(vals[0], y[0])                                                                                                      
        ohlc = bq.OHLC(x=x, y=vals, marker='bar', scales={'x': self.sc_x, 'y': self.sc_y}, 
                            format='ohlc', opacities=[0.3 for i in x] )
        ohlc.color=[color]
        return ohlc
    
    def filter_change(self, change):
        '''plot passbands selected from checkboxes'''
        plot_filters = self.get_selected_filters(self.filter_items)
        scatt_marks = []
        #add scatter and error bars to array of marks
        for filt in plot_filters:
            #create scatterplot
            i =  self.filters.index(filt)
            scatter = self.plot_scatter(self.x[i], self.data[i], self.filter_button_colors[i], filt)
            scatt_marks.append(scatter)
            #create errorbars
            errorbars = self.plot_errorbar(self.x[i], self.data[i], self.err[i])
            errorbars.stroke = self.filter_button_colors[i]
            scatt_marks.append(errorbars)
        
        #update lightcurve plot so show points
        self.lightcurve.marks = scatt_marks

    def lightcurve_widget(self):
        '''Create light curve widget'''
        xax = bq.Axis(label='Time (MJD)', scale=self.sc_x,
                        grid_lines='solid',
                        label_location="middle")
        xax.tick_style={'stroke': 'black', 'font-size': 12}

        yax = bq.Axis(label='Magnitude', scale=self.sc_y,
                        orientation='vertical', tick_format='0.1f',
                        grid_lines='solid', label_location="middle")
        yax.tick_style={'stroke': 'black', 'font-size': 12}

        panzoom = bq.PanZoom(scales={'x': [self.sc_x], 'y': [self.sc_y]})
        return bq.Figure(axes=[xax, yax], marks=[],
                        layout=Layout(width='100%', height='auto'),
                        fig_margin = {'top': 0, 'bottom': 40, 'left': 50, 'right': 0},
                         legend_location='top-right',
                         )

    @out.capture()
    def plot_images(self, plot, target):
        '''Create list of images'''
        i =  self.filter_button_colors.index(plot.colors[0])

        self.image_box.children = [self.diffImage[i][target['data']['index']], self.sciImage[i][target['data']['index']], 
                                   self.tempImage[i][target['data']['index']]]


    def print_event(self, target):
        print(target)

    def initialize_widget(self):
        '''Setup layout of the widget'''
       
        #define span and size of widgets
        title_layout = Layout(
            display='flex',
            flex_flow='column',
            justify_content='flex-end',
            width='100%',
            height='70',)
 
        fullspan_layout = Layout(
            display='flex',
            flex_flow='row',
            align_items='stretch',
            justify_content='center',
            width='100%',
            height='70',
        )
        eighty_span_layout = Layout(
            display='flex',
            flex_flow='row',
            justify_content='flex-start',
            width='80%',
            height='280px',
        )
        twenty_span_layout = Layout(
            display='flex',
            flex_flow='column',
            justify_content='center',
            width='20%',
            height='280px',
        )

        #create widgets using layout
        self.set_title('')           
        self.title_box = w.Box(children=self.title_items, layout=title_layout)
        self.filter_box = w.Box(children=self.filter_items, layout=fullspan_layout)                                                                
        self.lightcurve = self.lightcurve_widget()
        self.scatter_box = Box(children=[self.lightcurve], layout=eighty_span_layout) 
        self.image_box = Box(children=[], layout=twenty_span_layout)   
        
        #self.fold_radiobutton()
        self.plot_box = w.HBox([self.scatter_box,self.image_box])
        #position widgets using widget size
        self.widget = w.VBox([self.title_box, self.filter_box,self.plot_box], layout=w.Layout(height='350px'))

    def plot(self):
        '''plot display'''
        display(self.widget)

    def loadZTF(self, ztf, initial_filt='R'):
        '''Plot a ZTF object'''
        self.set_title(ztf.objectId) 
        

        #partition data by filter
        for filt in ztf.filterDict.keys():
            index = getattr(ztf, filt)
            self.x.append(ztf.time.loc[index].values)
            self.data.append(ztf.magpsf.loc[index].values)
            self.err.append(ztf.sigmapsf.loc[index].values)
            if (len(ztf.scienceImageArray) != 0):
                imageList = [ztf.scienceImageArray[i] for i in index.values]
                self.sciImage.append(imageList)
                imageList = [ztf.diffImageArray[i] for i in index.values]
                self.diffImage.append(imageList)
                imageList = [ztf.templateImageArray[i] for i in index.values]
                self.tempImage.append(imageList)
        
        self.x = np.asarray(self.x)
        self.data = np.asarray(self.data)
        self.err = np.asarray(self.err)
        
        #define which data set to plot
        i =  self.filters.index(initial_filt)
        self.filter_items[i].value = True
