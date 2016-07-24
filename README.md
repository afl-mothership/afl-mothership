#AFL Mothership

## Launching fuzzers
```
ec2-request-spot-instances ami-f5f41398 --price 0.15 -t c3.large \
--valid-until 2016-07-04T23:23:18.000Z -z us-west-1c -k mothership -g mothership \
--user-data-file ./cloud-init.sh \
-n 4 --availability-zone-group "ImageMagick-6.7.0-identify-bmp-8-fuzzers"
```

```
ec2-request-spot-instances ami-6e84fa0e --price 0.15 -t c3.large \
--valid-until 2016-07-10T23:23:18.000Z -z us-west-1c -k "mothership keypair (us-west)" \
-g mothership --user-data-file ./cloud-init.sh -n 4 \
-availability-zone-group "libarchive 2.2.1 bstdar | 8 fuzzers"
```