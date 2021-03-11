#!/usr/bin/env bash 
# 
# Origin from: https://github.com/RichardBronosky/ota-tools
# Modified by codeskyblue 2020/06/22
# Modified by codeskyblue 2020/08/14
#
# list identify
# security find-identity -v -p codesigning
#
# mobileprovision file can be found in
# ~/Library/MobileDevice/Provisioning\ Profiles/*.mobileprovision
#
# Thanks:
# https://github.com/DanTheMan827/ios-app-signer
#
# Relative docs:
# https://www.jianshu.com/p/7d352a648d13
#

set -o errexit
set -o pipefail

INSPECT_ONLY=0
if [[ "$1" == '-i' ]]; then
	INSPECT_ONLY=1
	shift
fi

if [[ "$1" == '-l' ]]; then
	security find-certificate -a | awk '/^keychain/ {if(k!=$0){print; k=$0;}} /"labl"<blob>=/{sub(".*<blob>=","          "); print}'
	exit
fi

if [[ ! ( # any of the following are not true
		# 1st arg is an existing regular file
		-f "$1" &&
		# ...and it has a .ipa extension
		"${1##*.}" == "ipa" &&
		# 2nd arg is an existing regular file
		($INSPECT_ONLY == 1 || -f "$2") &&
		# ...and it has an .mobileprovision extension
		($INSPECT_ONLY == 1 || "${2##*.}" == "mobileprovision") &&
		# 3rd arg is a non-empty string
		($INSPECT_ONLY == 1 || -n "$3")
		) ]];
	then
		cat << EOF >&2
	Usage: $(basename "$0") Application.ipa foo/bar.mobileprovision "iPhone Distribution: I can haz code signed"
	Usage: $(basename "$0") -i Application.ipa

	Options:
	  -i    Only inspect the package. Do not resign it.
	  -l    List certificates and exit
EOF
	exit;
fi

## Exit on use of an uninitialized variable
set -o nounset
## Exit if any statement returns a non-true return value (non-zero)
set -o errexit
## Announce commands
#set -o xtrace

realpath(){
	echo "$(cd "$(dirname "$1")"; echo -n "$(pwd)/$(basename "$1")")";
}

IPA="$(realpath $1)"
TMP="$(mktemp -d /tmp/resign.$(basename "$IPA" .ipa).XXXXX)"
IPA_NEW="$(pwd)/$(basename "$IPA" .ipa).resigned.ipa"
CLEANUP_TEMP=0 # Do not remove this line or "set -o nounset" will error on checks below
#CLEANUP_TEMP=1 # Uncomment this line if you want this script to clean up after itself
cd "$TMP"
[[ $CLEANUP_TEMP -ne 1 ]] && echo "Using temp dir: $TMP"
unzip -q "$IPA"

plutil -convert xml1 Payload/*.app/Info.plist -o Info.plist
echo "App has BundleDisplayName '$(/usr/libexec/PlistBuddy -c 'Print :CFBundleDisplayName' Info.plist)' and BundleShortVersionString '$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' Info.plist)'"
echo "App has BundleIdentifier  '$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' Info.plist)' and BundleVersion $(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' Info.plist)"
security cms -D -i Payload/*.app/embedded.mobileprovision 2>/dev/null > mobileprovision.plist
echo "App has provision         '$(/usr/libexec/PlistBuddy -c "Print :Name" mobileprovision.plist)', which supports '$(/usr/libexec/PlistBuddy -c "Print :Entitlements:application-identifier" mobileprovision.plist)'"

if [[ ! ($INSPECT_ONLY == 1) ]]; then
	PROVISION="$(realpath "$2")"
	CERTIFICATE="$3"
	security cms -D -i "$PROVISION" 2>/dev/null> provision.plist
	/usr/libexec/PlistBuddy  -x -c 'Print :Entitlements' provision.plist > entitlements.plist
	echo "Embedding provision       '$(/usr/libexec/PlistBuddy -c "Print :Name" provision.plist)', which supports '$(/usr/libexec/PlistBuddy -c "Print :Entitlements:application-identifier" provision.plist)'"

	# Remove old signatures
	#rm -rfv Payload/*.app/_CodeSignature Payload/*.app/CodeResources

	# Ref: https://stackoverflow.com/questions/5160863/how-to-re-sign-the-ipa-file
	# Re-sign embedded frameworks

	# Replace embedded provisioning profile
	cp "$PROVISION" Payload/*.app/embedded.mobileprovision

	find Payload -type d -name "_CodeSignature" | tail -r | while read -r CODESIGDIR
	do
		SIGNFOLDER=$(dirname "$CODESIGDIR")
		echo "CodeSigning -- $SIGNFOLDER"
		rm -rf "$CODESIGDIR"
		/usr/bin/codesign -f -s "$CERTIFICATE" --entitlements entitlements.plist "$SIGNFOLDER"
	done

	zip -qr "$IPA_NEW" Payload
	echo "Resigned IPA saved to $IPA_NEW"
fi
if [[ $CLEANUP_TEMP -eq 1 ]]; then
	rm -rf "$TMP"
fi
