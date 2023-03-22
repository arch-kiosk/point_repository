function initPointRepository() {
  console.log("point repository initialized.")
  initPointRepositoryHeaders()
  initPointRepositoryUploader()
}

function initPointRepositoryHeaders() {
  $('.pr-point-header').each(function () {
    if (this.innerText !== 'actions') {
      $(this).on("click", (e) => {
        let sort_by = $(this).attr("sort-field")
        let sort_order = $($(this).children()[1]).hasClass('fa-sort-up') ? 'dsc' : 'asc'
        $("#sort-by").val(sort_by)
        $("#sort-order").val(sort_order)
        $("#sort-form").submit()
      })
    }
  })
}

function initPointRepositoryUploader() {
  let maxUploadSizeMb = 5

  if ($("#max-upload-size-mb").length) {
    maxUploadSizeMb = Number($("#max-upload-size-mb").attr("max-upload-size-mb"))
  }
  let route = join_route(getRoutefor("pointrepository.pointrepository_show"), 'upload')
  console.log(route)
  // route = join_route(route, topic)
  $('#pr-drop-area-div').dmUploader({
    url: route,
    auto: true,
    queue: false,
    dataType: 'json',
    extFilter: ["csv", "txt", "xls", "xlsm", "xlsx"],
    multiple: false,
    maxFileSize: maxUploadSizeMb * 1024 * 1024,
    onBeforeUpload: function (id) {
      setPointRepositoryInstallUploadProgress(id, 0);
    },
    onUploadProgress: function (id, percent) {
      setPointRepositoryInstallUploadProgress(id, percent);
    },
    onUploadSuccess: function (id, data) {
      $("#pr-upload-progress").text(`Please drag a file here or click to upload`);
      if (data.success) {
        kioskSuccessToast(data.message,{
            timeout: 5000,
            onClosed: uploadFinished
          })
      }
      else {
        kioskErrorToast(`The upload failed (${data.message}). Please try again.`, {
            timeout: 5000,
            onClosed: uploadFinished
          })
      }
    },
    onUploadError: function (id, xhr, status, errorThrown) {
      console.log(xhr)
      console.log(status)
      console.log(errorThrown)

      $.magnificPopup.close()
      if (errorThrown) {
        kioskErrorToast(`The upload failed (${errorThrown}). Please try again.`,{
            timeout: 5000,
            onClosed: uploadFinished
          })
      }
      else
        kioskErrorToast(`The upload failed. Please try again.`, {
            timeout: 5000,
            onClosed: uploadFinished
          })
    },
    onFallbackMode: function (message) {
      kioskErrorToast('The upload failed because your Browser does not support it: ' + message, {
            timeout: 5000,
            onClosed: uploadFinished
          });
    },
    onFileSizeError: function (file) {
      kioskErrorToast(`The selected file exceeds the file size limit of ${maxUploadSizeMb} MBytes`)
    },
    onFileExtError: function (file) {
      kioskErrorToast(`Please upload only files with the extension csv, txt or some Excel file extension.`)
    },


  });

}

function setPointRepositoryInstallUploadProgress(id, percent) {
  $("#pr-upload-progress").text(`${percent} % done`);
}

function uploadFinished (instance, toast, closedBy) {
  location.reload()
}
