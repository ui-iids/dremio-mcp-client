#!/usr/bin/env bash
while getopts a:n:u:d: flag
do
    case "${flag}" in
        a) author=${OPTARG};;
        n) name=${OPTARG};;
        u) urlname=${OPTARG};;
        d) description=${OPTARG};;
    esac
done

echo "Author: $author";
echo "Project Name: $name";
echo "Project URL name: $urlname";
echo "Description: $description";

echo "Renaming project..."

original_author="author_name"
original_name="project_name"
original_dash_name="project-name"
original_urlname="project_urlname"
original_description="project_description"

# Convert underscores to dashes, and upper to lowercase
dash_name=$(echo $name | tr '[:upper:]' '[:lower:]' | tr '_' '-')
underscore_name=$(echo $name | tr '[:upper:]' '[:lower:]' | tr '-' '_')
# for filename in $(find . -name "*.*") 
for filename in $(git ls-files) 
do
    sed -i "s/$original_author/$author/g" $filename
    sed -i "s/$original_name/$underscore_name/g" $filename
    sed -i "s/$original_dash_name/$dash_name/g" $filename
    sed -i "s/$original_urlname/$urlname/g" $filename
    sed -i "s/$original_description/$description/g" $filename
    echo "Renamed $filename"
done

mv project_name $underscore_name
mv -f project_templates/* .

# This command runs only once on GHA!
rm -rf .github/template.yml
