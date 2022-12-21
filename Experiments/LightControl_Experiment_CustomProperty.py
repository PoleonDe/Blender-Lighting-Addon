import bpy

class AddCustomPropertyToObject(bpy.types.Operator):
    """Create a Light and Empty"""
    bl_idname = "object.add_custom_property"
    bl_label = "Add a custom Property to an Object"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        # Add new Empty Object
        emptyObject = bpy.data.objects.new("ObjectName", None)
        # Custom Property
        emptyObject["pivotPoint"] = (1,2,3)
        # link empty to Scene
        bpy.context.scene.collection.objects.link(emptyObject)

        if "pivotPoint" in emptyObject:
            print("pivotPoint is Property found")
            val = emptyObject["pivotPoint"]
            print(f"pivotPoint is {val[0]} {val[1]} {val[2]}")
            emptyObject["pivotPoint"] = (10,5,1)
            print(f"pivotPoint is {val[0]} {val[1]} {val[2]}")

        print("CustomPropertyInvoked")
        return {'FINISHED'}

def register():
    print("registered")
    bpy.utils.register_class(AddCustomPropertyToObject)

def unregister():
    print("unregistered")
    bpy.utils.unregister_class(AddCustomPropertyToObject)

# TestRunning
if __name__ == '__main__':
    register()


# bpy.context.object["MyOwnProperty"] = 42

# if "SomeProp" in bpy.context.object:
#     print("Property found")

# # Use the get function like a Python dictionary
# # which can have a fallback value.
# value = bpy.data.scenes["Scene"].get("test_prop", "fallback value")

# # dictionaries can be assigned as long as they only use basic types.
# group = bpy.data.groups.new("MyTestGroup")
# group["GameSettings"] = {"foo": 10, "bar": "spam", "baz": {}}

# del group["GameSettings"]

#
#
#
# CALL AN OPERTATOR FROM AN OPERATOR
#
#
#