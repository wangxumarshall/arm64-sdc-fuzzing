#!/usr/bin/env perl

# Copyright 2026 Intel Corporation.
# SPDX-License-Identifier: Apache-2.0

use strict;
use warnings;

$\ = "\n";
$/ = "\n";

sub sanitize_id
{
    my ($value) = @_;
    $value = lc($value);
    $value =~ s/[^a-z0-9_]/_/g;
    return $value;
}

sub uppercase_id
{
    my ($value) = @_;
    $value = uc($value);
    $value =~ s/[^A-Z0-9_]/_/g;
    return $value;
}

sub pretty_arch_name
{
    my ($name) = @_;
    my %special = (
        'aes' => 'AES',
        'armv8' => 'Armv8',
        'armv9' => 'Armv9',
        'asimd' => 'ASIMD',
        'crc' => 'CRC',
        'crc32' => 'CRC32',
        'crypto' => 'Crypto',
        'fp' => 'FP',
        'neon' => 'NEON',
        'pmull' => 'PMULL',
        'sha1' => 'SHA1',
        'sha2' => 'SHA2',
        'sve' => 'SVE',
        'sve2' => 'SVE2',
    );

    my @parts = split /_/, $name;
    @parts = map {
        my $key = lc($_);
        exists $special{$key} ? $special{$key} : ucfirst($key);
    } @parts;
    return join(' ', @parts);
}

my $input_conf_file = shift @ARGV;
open(my $fh, '<', $input_conf_file) or die $!;

my @features;
my %feature_ids;
my @architecture_names;
my %architectures;
my $maxarchnamelen = 0;

while (<$fh>) {
    chomp;
    my $comment = "";
    if (/\#\s*(.*)\s*$/) {
        $comment = $1;
    }

    s/\#.*$//;
    s/^\s+//;
    s/\s+$//;
    next if $_ eq "";

    if (s/^arch=//) {
        my ($arch, $base, $feature_list) = split /\s+/, $_, 3;
        die("Malformed arch line: $_") unless defined $arch && defined $base;

        die("Unknown base architecture \"$base\"")
            unless $base eq "<>" or grep { $_ eq $base } @architecture_names;

        my @basefeatures;
        @basefeatures = @{$architectures{$base}->{allfeatures}} if $base ne "<>";

        my @extrafeatures;
        my $is_alias = 0;
        if (defined $feature_list && $feature_list ne "") {
            if ($feature_list eq "alias") {
                # Pure alias: inherits base's full feature set, adds nothing.
                # Generates the cpu_<id> #define so source referencing the
                # symbol compiles, but is excluded from the runtime
                # arm64_architectures[] array (see below) to avoid emitting
                # non-ARM64 architecture names in "Detected CPU:" output.
                $is_alias = 1;
            } else {
                @extrafeatures = grep { $_ ne "" } split /,/, $feature_list;
            }
        }

        for my $feature_name (@extrafeatures) {
            die("Unknown feature \"$feature_name\" for architecture \"$arch\"")
                unless exists $feature_ids{$feature_name};
        }

        my %seen;
        my @allfeatures = grep { !$seen{$_}++ } (@basefeatures, @extrafeatures);
        my @sortedfeatures = sort { $feature_ids{$a} <=> $feature_ids{$b} } @allfeatures;

        my $id = sanitize_id($arch);
        my $prettyname = pretty_arch_name($arch);
        $maxarchnamelen = length($prettyname) if length($prettyname) > $maxarchnamelen;

        $architectures{$arch} = {
            name => $arch,
            prettyname => $prettyname,
            id => $id,
            base => $base,
            features => \@extrafeatures,
            allfeatures => \@sortedfeatures,
            comment => $comment,
            is_alias => $is_alias,
        };
        push @architecture_names, $arch
            unless grep { $_ eq $arch } @architecture_names;
        next;
    }

    my ($name, $source, $bit, $compiler_macro) = split /\s+/, $_, 4;
    die("Malformed feature line: $_")
        unless defined $name && defined $source && defined $bit;

    die("Unknown source \"$source\"")
        unless $source eq "HWCAP" or $source eq "HWCAP2";

    die("Duplicate feature \"$name\"")
        if exists $feature_ids{$name};

    $compiler_macro = '-' unless defined $compiler_macro && $compiler_macro ne "";

    my $id = uppercase_id($name);
    push @features, {
        name => $name,
        id => $id,
        source => $source,
        bit => int($bit),
        compiler_macro => $compiler_macro,
        comment => $comment,
    };
    $feature_ids{$name} = scalar(@features) - 1;
}
close($fh);

my $feature_count = scalar @features;
die("No features defined in $input_conf_file") if $feature_count == 0;
die("Too many features to fit a 128-bit integer") if $feature_count > 128;

my $feature_type = "uint64_t";
$feature_type = "unsigned __int128" if $feature_count > 64;

my $headername = shift @ARGV;
my $headerguard = uc($headername || "cpu_features_h");
$headerguard =~ s/[^A-Z0-9_]/_/g;

print qq|// This is a generated file. DO NOT EDIT.
// Please see $0
#ifndef $headerguard
#define $headerguard

#include <stdint.h>
|;

print "typedef $feature_type device_features_t;";
print "#define CPU_FEATURE_CONSTANT(bit) (((device_features_t) 1) << (bit))";

for (my $i = 0; $i < scalar @features; ++$i) {
    my $feature = $features[$i];
    print sprintf "#define cpu_feature_%-27s (CPU_FEATURE_CONSTANT(%d))", lc($feature->{id}), $i;
}

print "";
print "// ARM64 architecture / profile aggregates";
for my $arch_name (@architecture_names) {
    my $arch = $architectures{$arch_name};
    my $base = $arch->{base} eq "<>" ? "0" : "cpu_" . sanitize_id($arch->{base});

    printf "#define cpu_%-27s (%s", $arch->{id}, $base;
    for my $feature_name (@{$arch->{features}}) {
        my $feature = $features[$feature_ids{$feature_name}];
        printf " \\\n%33s| cpu_feature_%s", " ", lc($feature->{id});
    }
    print ")";
}

print "";
print "static const device_features_t device_compiler_features = 0";
for my $feature (@features) {
    next if $feature->{compiler_macro} eq '-';
    print sprintf "#ifdef %s", $feature->{compiler_macro};
    print sprintf "         | cpu_feature_%s", lc($feature->{id});
    print "#endif";
}
print "        ;";

print "// -- implementation start --";
my $offset = 0;
my @offsets;
print "static const char features_string[] =";
for my $feature (@features) {
    print "    \" $feature->{name}\\0\"";
    push @offsets, $offset;
    $offset += 2 + length($feature->{name});
}
print "    \"\\0\";";

printf "\nstatic const %s features_indices[] = {",
    $offset > 255 ? "uint16_t" : "uint8_t";
for (my $j = 0; $j < scalar @offsets; ++$j) {
    printf "%s%3d,",
        $j % 8 ? " " : "\n    ", $offsets[$j];
}
print "\n};";

print qq|
enum Arm64HwcapSource {
    Arm64Hwcap = 0,
    Arm64Hwcap2 = 1,
    Arm64HwcapMax
};

struct Arm64HwcapLocator
{
    uint8_t source;
    uint8_t bit;
};

static const struct Arm64HwcapLocator arm64_locators[] = {|;
for my $feature (@features) {
    my $source = $feature->{source} eq "HWCAP2" ? "Arm64Hwcap2" : "Arm64Hwcap";
    print sprintf "    { %-11s, %2d }, // %s", $source, $feature->{bit}, $feature->{name};
}
print "};";

print qq|
struct Arm64Architecture
{
    device_features_t features;
    char name[$maxarchnamelen + 1];
};

static const struct Arm64Architecture arm64_architectures[] = {|;
my %seen_arch_signatures;
for my $arch_name (reverse @architecture_names) {
    my $arch = $architectures{$arch_name};
    next if $arch->{is_alias};   # alias-only: #define emitted, but not in runtime array
    my $signature = join(',', @{$arch->{allfeatures}});
    next if exists $seen_arch_signatures{$signature};
    $seen_arch_signatures{$signature} = 1;
    print sprintf "    { cpu_%s, \"%s\" },", $arch->{id}, $arch->{prettyname};
}
print "};";

print qq|

// -- implementation end --
#endif /* $headerguard */
|;
