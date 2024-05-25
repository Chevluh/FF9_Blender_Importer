# FF9 Blender Importer
A Blender importer for models used in the PS1 version of Final Fantasy IX

Features
--------

This add-on can import animated and weapon models used in the PS1 version of FF9. Player characters, monsters and weapons are well supported and are imported with textures and bone animations.

All animations are imported together as a single action, and the scene's end frame will be adjusted to match the end of the action.

Support for overworld and field characters is only partial and a work in progress. All the models in a given file will be imported in one go, and each model is matched with all compatible animations.

Additionally, texture animation is not supported for any model.

FF9 models are stored in bone space so be aware that models' rest poses don't look like anything.

Installation & Usage
--------

- Put the python file in Blender's addon directory and restart Blender
- Activate the add-on under *Edit > Preferences > Add-ons > Import-Export: Import Final Fantasy 9 models*
- "FF9 model (ff9.img)" should appear in the import menu
- After choosing the ff9.IMG file that you can find on any of the PS1 FF9 discs, choose the directory and model file index. Supported directories are 3 (overworld models), 4 (field models), 7 (enemy models), 8 (weapons) and 10 (player party models). Note that importing from directory 4 can take a while as each model will be matched with all animations

Have fun exploring!

None of this would have been possible without the hard work of everyone on the Qhimm.com forum, who figured out most aspects of the format used here.