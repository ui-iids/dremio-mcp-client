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

original_author="ViaJables"
original_name="dremio_mcp_client"
original_dash_name="dremio-mcp-client"
original_urlname="dremio-mcp-client"
original_description="dremio_mcp_client created by ViaJables"

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

mv dremio_mcp_client $underscore_name
mv -f project_templates/* .

# This command runs only once on GHA!
rm -rf .github/template.yml
