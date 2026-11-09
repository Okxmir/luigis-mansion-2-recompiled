#include "lm2_services.h"

#include "hle/service.h"

namespace {
class LocalDownloadPlay final : public hle::Service {
public:
    LocalDownloadPlay() : Service("dlp:SRVR") {}

    void handle(hle::Request &req) override {
        if (req.header() != 0x000e0040) hle::unimplemented(*this, req);
        // IsChild(node). The local cartridge process has no Download Play session.
        req.reply(2, 0).push(0);
    }
};
}

void register_lm2_services() {
    hle::register_service({"dlp:SRVR"}, std::make_shared<LocalDownloadPlay>());
}
